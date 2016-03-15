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

#-------------------------------------------------------------------------------    
@celery_app.task
def process(entries, keys):
    # Celery process that sends email receipts to entries in Route 
    # Importer->Routes worksheet. Lots of account data retrieved from eTap 
    # (accounts + journal data) so can take awhile to run 4 templates: 
    # gift_collection, zero_collection, dropoff_followup, cancelled entries: 
    # list of row entries to receive emailed receipts
    try:
        # Get all eTapestry account data
        accounts = etap.call('get_accounts', keys, {
          "account_numbers": [i['account_number'] for i in entries]
        })
    except Exception as e:
        logger.error('Error retrieving accounts from etap')
        return False
    
    # Update 'Email Status' with either 'queued' or 'no email' so user knows process is running 
    
    gc = auth(['https://spreadsheets.google.com/feeds'])
    wks = gc.open('Route Importer').worksheet('Routes')
    headers = wks.row_values(1)
    
    start = wks.get_addr_int(2, headers.index('Email Status')+1)
    end = start[0] + str(len(accounts)+1)
    status_range = wks.range(start + ':' + end)

    for i in xrange(len(accounts) - 1, -1, -1):
        if 'email' not in accounts[i]:
            status_range[i].value = 'no email'
            del accounts[i]
            del entries[i]
        else:
            entries[i]['etap_account'] = accounts[i]
            status_range[i].value = 'queued'
  
    wks.update_cells(status_range)

    gift_accounts = []
    num_zero_receipts = 0
    num_dropoff_followups = 0
    num_cancelled = 0

    # Send Dropoff Followups, Zero Collection, and Cancelled email receipts 
    for entry in entries:
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

#-------------------------------------------------------------------------------  
def send_gift_receipts():
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
