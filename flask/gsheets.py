import json
from oauth2client.client import SignedJwtAssertionCredentials
import gspread
import flask
import requests
from datetime import datetime
from flask import request, current_app, render_template
from dateutil.parser import parse

import scheduler
import etap
from app import flask_app, celery_app, db, logger
from config import *

ZERO_COLLECTION_EMAIL_SUBJECT = 'We missed your pickup this time around'
DROPOFF_FOLLOWUP_EMAIL_SUBJECT = 'Your Dropoff is Complete'
GIFT_RECEIPT_EMAIL_SUBJECT = 'Thanks for your donation!'
WELCOME_EMAIL_SUBJECT = 'Welcome to Empties to Winn'
CANCELLED_EMAIL_SUBJECT = 'You have been removed from the collection schedule'

# scope is array of Google service URL's to authorize
def auth(scope):
  try:
    json_key = json.load(open('oauth_credentials.json'))
    credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)
    return gspread.authorize(credentials)
  except Exception as e:
    logger.info('gsheets.auth():', exc_info=True)
    return False
    
# Celery process that sends email receipts to entries in Route Importer->Routes worksheet
# Lots of account data retrieved from eTap (accounts + journal data) so can take awhile to run 
# 4 templates: gift_collection, zero_collection, dropoff_followup, cancelled
# entries: list of row entries to receive emailed receipts
@celery_app.task
def process_receipts(entries, keys):
  try:
    # Get all eTapestry account data
    accounts = etap.call('get_accounts', keys, {
      "account_numbers": [i['account_number'] for i in entries]
    })
    
    # Update 'Email Status' with either 'queued' or 'no email' so user knows process is running 
    
    gc = auth(['https://spreadsheets.google.com/feeds'])
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
    num_cancelled = 0

    # Send Dropoff Followups, Zero Collection, and Cancelled email receipts 
    for entry in entries:
      if not entry['etap_account']['email']:
        continue

      status = etap.get_udf('Status', entry['etap_account'])
      
      args = {
        "account_number": entry['account_number'],
        "recipient": entry['etap_account']['email'],
        "name": entry['etap_account']['name'],
        "date": parse(entry['date']).strftime('%B %-d, %Y'),
        "address": entry["etap_account"]["address"],
        "postal": entry["etap_account"]["postalCode"],
        "sheet_name": "Route Importer",
        "worksheet_name": "Routes",
        "upload_status": entry["upload_status"],
        "row": entry["row"],
      }

      # Test for Cancel email
      if status == 'Cancelled':
        args['template'] = "email_cancelled.html"
        args['subject'] = CANCELLED_EMAIL_SUBJECT

        r = requests.post(PUB_URL + '/email/send', data=json.dumps(args))

        num_cancelled +=1
      
        continue

      # Test for Dropoff Followup email
      drop_date = etap.get_udf('Dropoff Date', entry['etap_account'])
      
      if drop_date:
        d = drop_date.split('/')
        drop_date = datetime(int(d[2]),int(d[1]),int(d[0])).date()
        collection_date = parse(entry['date']).date() #replace(tzinfo=None)
        
        if drop_date == collection_date:
          args["template"] = "email_dropoff_followup.html"
          args["subject"] = DROPOFF_FOLLOWUP_EMAIL_SUBJECT
          
          if entry['next_pickup']:
            args['next_pickup'] = parse(entry['next_pickup']).strftime('%B %-d, %Y')

          r = requests.post(PUB_URL + '/email/send', data=json.dumps(args))

          num_dropoff_followups += 1
          
          continue

      # Test for Zero Collection or Gift Collection email
      if entry['amount'] == 0:
        args['template'] = "email_zero_collection.html"
        args['subject'] = ZERO_COLLECTION_EMAIL_SUBJECT
        if entry['next_pickup']:
          args['next_pickup'] = parse(entry['next_pickup']).strftime('%B %-d, %Y')

        r = requests.post(PUB_URL + '/email/send', data=json.dumps(args))

        num_zero_receipts+=1
      else:
          # Can't send these yet, don't have gift histories. Build list to query
          # them at once for speed 
          gift_accounts.append(entry)

    # Call eTap 'get_gift_history' for non-zero donations
    # Send Gift receipts

    if(len(gift_accounts)) == 0:
      return 'OK'

    year = parse(gift_accounts[0]['date']).year

    gift_histories = etap.call('get_gift_histories', keys, {
      "account_refs": [i['etap_account']['ref'] for i in gift_accounts],
      "start_date": "01/01/" + str(year),
      "end_date": "31/12/" + str(year)
    })
    
    num_gift_receipts = 0

    for idx, entry in enumerate(gift_accounts):
      gifts = gift_histories[idx]

      for gift in gifts:
        gift['date'] = parse(gift['date']).strftime('%B %-d, %Y')
        gift['amount'] = '$' + str(gift['amount'])

      num_gift_receipts += 1

      args = {
        "account_number": entry['account_number'],
        "recipient": entry['etap_account']['email'],
        "name": entry['etap_account']['name'],
        "last_date": parse(entry['date']).strftime('%B %-d, %Y'),
        "last_amount": '$' + str(entry['amount']),
        "gift_history": gifts,
        "sheet_name": "Route Importer",
        "worksheet_name": "Routes",
        "upload_status": entry["upload_status"],
        "row": entry["row"],
        "template": "email_collection_receipt.html",
        "subject": GIFT_RECEIPT_EMAIL_SUBJECT
      }

      if entry['next_pickup']:
        args['next_pickup'] = parse(entry['next_pickup']).strftime('%B %-d, %Y')

      # Send requests.post back to Flask
      r = requests.post(PUB_URL + '/email/send', data=json.dumps(args))

    logger.info('Receipts: \n' +
      str(num_zero_receipts) + ' zero collections sent\n' +
      str(num_gift_receipts) + ' gift receipts sent\n' +
      str(num_dropoff_followups) + ' dropoff followups sent\n' +
      str(num_cancelled) + ' cancellations sent'
    )
            
    return 'OK'

  except Exception, e:
    logger.error('send_receipts', exc_info=True)
    return str(e)


def update_entry(db_record):
  gc = auth(['https://spreadsheets.google.com/feeds'])
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
  gc = auth(['https://spreadsheets.google.com/feeds'])
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
    gc = auth(['https://spreadsheets.google.com/feeds'])
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
    logger.info('add_signup_row. data: ' + json.dumps(signup), exc_info=True)
    return str(e)
