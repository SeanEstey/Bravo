import json
from oauth2client.client import SignedJwtAssertionCredentials
import gspread
import flask
import requests
from flask import request, current_app, render_template
from dateutil.parser import parse

from app import flask_app, celery_app, db, logger
from server_settings import *

@celery_app.task
def send_receipts(entries, keys):
  try:
    # Call eTap 'get_accounts' func for all accounts
    account_numbers = []
    url = 'http://www.bravoweb.ca/etap/etap_mongo.php'

    for entry in entries:
      account_numbers.append(entry['account_number'])

    r = requests.post(url, data=json.dumps({
      "func": "get_accounts",
      "keys": keys,
      "data": {
        "account_numbers": account_numbers
      }
    }))

    accounts = json.loads(r.text)
    
    json_key = json.load(open('oauth_credentials.json'))
    scope = ['https://spreadsheets.google.com/feeds', 'https://docs.google.com/feeds']
    credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)
    gc = gspread.authorize(credentials)
  
    wks = gc.open('Route Importer').worksheet('Routes')
    headers = wks.row_values(1)
    
    start = wks.get_addr_int(2, headers.index('Email Status')+1)
    end = start[0] + str(len(accounts)+1)
    email_status_cells = wks.range(start + ':' + end)

    for idx, entry in enumerate(entries):
      entry['etap_account'] = accounts[idx]
      
      if accounts[idx]['email']:
        email_status_cells[idx].value = 'queued'
      else:
        email_status_cells[idx].value = 'no email'
      
    wks.update_cells(email_status_cells)

    # Send Zero Collection receipts 
    
    for entry in entries:
      if entry['amount'] == 0 and entry['etap_account']['email']:
        r = requests.post(PUB_URL + '/send_zero_receipt', data=json.dumps({
            "account_number": entry['account_number'],
            "email": entry['etap_account']['email'],
            "first_name": entry['etap_account']['firstName'],
            "date": entry["date"],
            "address": entry["etap_account"]["address"],
            "postal": entry["etap_account"]["postalCode"],
            "next_pickup": entry["next_pickup"],
            "row": entry["row"],
            "upload_status": entry["upload_status"]
        }))

        entries.remove(entry)

    # 'entries' list should now contain only gifts
    # Call eTap 'get_gift_history' for non-zero donations
    # Send Gift receipts

    account_refs = []

    year = parse(entry[0]['date']).year

    for entry in entries:
      account_refs.append(entry['etap_account']['ref'])

    r = requests.post(url, data=json.dumps({
      "func": "get_gift_histories",
      "keys": keys,
      "data": {
        "account_refs": account_refs,
        "start_date": "01/01/" + year,
        "end_date": "31/12/" + year
      }
    }))

    gift_histories = json.loads(r.text)

    for idx, entry in enumerate(entries):
      gifts = gift_histories[idx]

      if entry['etap_account']['email']:
        for gift in gifts:
          gift['date'] = parse(gift['date']).strftime('%B %-d, %Y')
          gift['amount'] = '$' + str(gift['amount'])

        # Send requests.post back to Flask
        r = requests.post(PUB_URL + '/send_gift_receipt', data=json.dumps({
            "account_number": entry['account_number'],
            "email": entry['etap_account']['email'],
            "first_name": entry['etap_account']['firstName'],
            "last_date": parse(entry['date']).strftime('%B %-d, %Y'),
            "last_amount": '$' + str(entry['amount']),
            "gift_history": gifts,
            "next_pickup": parse(entry['next_pickup']).strftime('%B %-d, %Y'),
            "row": entry['row'],
            "upload_status": entry["upload_status"]
        }))

    return 'OK'

  except Exception, e:
    logger.error('send_receipts', exc_info=True)
    return str(e)


def update_entry(db_record):
  json_key = json.load(open('oauth_credentials.json'))
  scope = ['https://spreadsheets.google.com/feeds', 'https://docs.google.com/feeds']
  credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)
  gc = gspread.authorize(credentials)
  
  sheet = gc.open(db_record['sheet_name'])
  wks = sheet.worksheet(db_record['worksheet_name'])

  headers = wks.row_values(1)
  
  # Make sure the row entry still exists in the worksheet
  cell = wks.cell(db_record['row'], headers.index('Upload Status')+1)

  if cell:
    if str(cell.value) == db_record['upload_status']:
      wks.update_cell(db_record['row'], headers.index('Email Status')+1, db_record['status'])

  # Create RFU if event is dropped/bounced and is from a collection receipt
  if db_record['worksheet_name'] == 'Routes':
      if db_record['status'] == 'dropped' or db_record['status'] == 'bounced':
        wks = sheet.worksheet('RFU')
        headers = wks.row_values(1)
        
        rfu = [''] * len(headers)
        rfu[headers.index('Request Note')] = 'Email ' + db_record['recipient'] + ' dropped.'

        if 'account_number' in db_record:
          rfu[headers.index('Account Number')] = db_record['account_number']

        logger.info('Creating RFU for bounced/dropped email: ' + json.dumps(rfu))
        wks.append_row(rfu)
