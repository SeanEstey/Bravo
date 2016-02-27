import json
from oauth2client.client import SignedJwtAssertionCredentials
import gspread
import flask
import requests
from datetime import datetime
from flask import request, current_app, render_template
from dateutil.parser import parse

import scheduler
from app import flask_app, celery_app, db, logger
from config import *

@celery_app.task
def send_receipts(entries, keys):
  try:
    # Call eTap 'get_accounts' func for all accounts
    account_numbers = []

    for entry in entries:
      account_numbers.append(entry['account_number'])

    r = requests.post(ETAP_WRAPPER_URL, data=json.dumps({
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

    gift_accounts = []
    num_zero_receipts = 0
    num_dropoff_followups = 0

    # Send Dropoff Followups, Zero Collection, and Cancel email receipts 
    for entry in entries:
      if not entry['etap_account']['email']:
        continue

      status = scheduler.get_udf('Status', entry['etap_account'])

      # Test for Cancel email
      if status == 'Cancelled':
        # TODO: send Cancel email confirmation
        continue

      # Test for Dropoff Followup email
      drop_date = scheduler.get_udf('Dropoff Date', entry['etap_account'])
      if drop_date:
        d = drop_date.split('/')
        drop_date = datetime(int(d[2]),int(d[1]),int(d[0])).date()
        collection_date = parse(entry['date']).date() #replace(tzinfo=None)
        if drop_date == collection_date:
          args = {
            "account_number": entry['account_number'],
            "email": entry['etap_account']['email'],
            "name": entry['etap_account']['name'],
            "date": parse(entry['date']).strftime('%B %-d, %Y'),
            "address": entry["etap_account"]["address"],
            "postal": entry["etap_account"]["postalCode"],
            "row": entry["row"],
            "upload_status": entry["upload_status"]
          }

          if entry['next_pickup']:
            args['next_pickup'] = parse(entry['next_pickup']).strftime('%B %-d, %Y')

          r = requests.post(PUB_URL + '/send_dropoff_followup', data=json.dumps(args))

          num_dropoff_followups += 1
          
          continue

      # Test for Zero Collection or Gift Collection email
      if entry['amount'] == 0:
        args = {
          "account_number": entry['account_number'],
          "email": entry['etap_account']['email'],
          "name": entry['etap_account']['name'],
          "date": parse(entry['date']).strftime('%B %-d, %Y'),
          "address": entry["etap_account"]["address"],
          "postal": entry["etap_account"]["postalCode"],
          "row": entry["row"],
          "upload_status": entry["upload_status"]
        }

        if entry['next_pickup']:
          args['next_pickup'] = parse(entry['next_pickup']).strftime('%B %-d, %Y')

        r = requests.post(PUB_URL + '/send_zero_receipt', data=json.dumps(args))

        num_zero_receipts+=1
      else:
          # Can't send these yet, don't have gift histories. Build list to query
          # them at once for speed 
          gift_accounts.append(entry)

    # 'entries' list should now contain only gifts
    # Call eTap 'get_gift_history' for non-zero donations
    # Send Gift receipts

    account_refs = []
    
    year = parse(gift_accounts[0]['date']).year

    for entry in gift_accounts:
      account_refs.append(entry['etap_account']['ref'])

    r = requests.post(ETAP_WRAPPER_URL, data=json.dumps({
      "func": "get_gift_histories",
      "keys": keys,
      "data": {
        "account_refs": account_refs,
        "start_date": "01/01/" + str(year),
        "end_date": "31/12/" + str(year)
      }
    }))

    gift_histories = json.loads(r.text)

    num_gift_receipts = 0

    for idx, entry in enumerate(gift_accounts):
      if not entry['etap_account']['email']:
        continue
      
      gifts = gift_histories[idx]

      for gift in gifts:
        gift['date'] = parse(gift['date']).strftime('%B %-d, %Y')
        gift['amount'] = '$' + str(gift['amount'])

      num_gift_receipts += 1

      args = {
        "account_number": entry['account_number'],
        "email": entry['etap_account']['email'],
        "name": entry['etap_account']['name'],
        "last_date": parse(entry['date']).strftime('%B %-d, %Y'),
        "last_amount": '$' + str(entry['amount']),
        "gift_history": gifts,
        "row": entry['row'],
        "upload_status": entry["upload_status"]
      }

      if entry['next_pickup']:
        args['next_pickup'] = parse(entry['next_pickup']).strftime('%B %-d, %Y')

      # Send requests.post back to Flask
      r = requests.post(PUB_URL + '/send_gift_receipt', data=json.dumps(args))

    logger.info(str(num_zero_receipts) + ' zero receipts sent, ' + str(num_gift_receipts) + ' gift receipts sent, ' + str(num_dropoff_followups) + ' dropoff followups sent')
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


def create_rfu(request_note, account_number=None, next_pickup=None, block=None, date=None):
  json_key = json.load(open('oauth_credentials.json'))
  scope = ['https://spreadsheets.google.com/feeds', 'https://docs.google.com/feeds']
  credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)
  gc = gspread.authorize(credentials)

  sheet = gc.open('Route Importer')
  wks = sheet.worksheet('RFU')
  
  headers = wks.row_values(1)

  rfu = [''] * len(headers)
  
  rfu[headers.index('Request Note')] = request_note
  
  if account_number != None:
    rfu[headers.index('Account Number')] = account_number

  if next_pickup != None:
    rfu[headers.index('Next Pickup Date')] = next_pickup

  if block != None:
    rfu[headers.index('Block')] = block

  if date != None:
    rfu[headers.index('Date')] = date

  logger.info('Creating RFU: ' + json.dumps([item for item in rfu if item]))
  wks.append_row(rfu)


@celery_app.task
def add_signup_row(signup):
  try:
    json_key = json.load(open('oauth_credentials.json'))
    scope = ['https://spreadsheets.google.com/feeds', 'https://docs.google.com/feeds']
    credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)
    gc = gspread.authorize(credentials)
    wks = gc.open('Route Importer').worksheet('Signups')

    form_data = {
      'Signup Date': datetime.now().strftime('%-m/%-d/%Y'),
      'Office Notes': signup['special_requests'],
      'Address': signup['address'],
      'Postal Code': signup['postal'],
      'Primary Phone': signup['phone'],
      'Email': signup['email'],
      'Tax Receipt': signup['tax_receipt'],
      'Reason Joined': signup['reason_joined'],
      'City': signup['city'],
      'Status': 'Dropoff'
    }

    if signup['account_type'] == 'Residential':
        form_data['First Name'] = signup['first_name']
        form_data['Last Name'] = signup['last_name']
        form_data['Name Format'] = 'Individual'
        form_data['Persona Type'] = 'Personal'
    elif signup['account_type'] == 'Business':
        form_data['Business Name'] = signup['account_name']
        form_data['Contact Person'] = signup['contact_person']
        form_data['Name Format'] = 'Business'
        form_data['Persona Type'] = 'Business'

    if 'title' in signup:
      form_data['Title'] = signup['title']
      
    if 'referrer' in signup:
      form_data['Referrer'] = signup['referrer']   

    headers = wks.row_values(1)
    row = []

    for field in headers:
      if form_data.has_key(field):
        row.append(form_data[field])
      else:
        row.append('')
    
    wks.append_row(row)
  
  except Exception, e:
    logger.info('add_signup_row', exc_info=True)
    return str(e)
