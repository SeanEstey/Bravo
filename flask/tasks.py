from config import *
from server_settings import *
from reminders import dial
from celery import Celery
from celery.signals import worker_process_init, task_prerun
import time
import os
from dateutil.parser import parse
from datetime import datetime,date
from bson.objectid import ObjectId
import pymongo
import twilio
from twilio import twiml
import logging
import requests
import json
import dateutil
import httplib2
from oauth2client.client import SignedJwtAssertionCredentials 
from apiclient.discovery import build
import gspread

logger = logging.getLogger(__name__)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(LOG_LEVEL)
handler.setFormatter(formatter)
logger.setLevel(LOG_LEVEL)
logger.addHandler(handler)
celery_app = Celery('tasks')
celery_app.config_from_object('config')
mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT, connect=False)
db = mongo_client[DB_NAME]

@celery_app.task
def no_pickup_etapestry(url, params):
  r = requests.get(url, params=params)
  
  if r.status_code != 200:
    logger.error('etap script "%s" failed. status_code:%i', url, r.status_code)
    return r.status_code
  
  logger.info('No pickup for account %s', params['account'])

  return r.status_code

@celery_app.task
def get_next_pickups(job_id):
  try:
    job_id = ObjectId(job_id)
    messages = db['msgs'].find({'job_id':job_id}, {'imported.block':1})
    blocks = []
    for msg in messages:
      if msg['imported']['block'] not in blocks:
        blocks.append(msg['imported']['block'])

    # Generated on google developer console
    f = file("google_api_key.p12", "rb")
    key = f.read()
    f.close()

    credentials = SignedJwtAssertionCredentials(
      service_account_name = GOOGLE_SERVICE_ACCOUNT,
      private_key = key,
      scope = 'https://www.googleapis.com/auth/calendar.readonly'
    )

    http = httplib2.Http()
    http = credentials.authorize(http)

    start_search = datetime.now() + timedelta(days=30)
    end_search = start_search + timedelta(days=70)

    service = build('calendar', 'v3', http=http)
    events = service.events().list(
      calendarId = ETW_RES_CALENDAR_ID,
      timeMin = start_search.isoformat()+'+01:00',
      timeMax = end_search.isoformat()+'+01:00',
      singleEvents = True,
      orderBy = 'startTime'
      #maxResults = 50
    ).execute()

    logger.info('%i calendar events pulled', len(events['items']))

    pickup_dates = {}
    for block in blocks:
      # Search calendar events to find pickup date
      for event in events['items']:
        cal_block = event['summary'].split(' ')[0]
        if cal_block == block:
          logger.debug('Block %s Pickup Date: %s', block, event['start']['date'])
          dt = dateutil.parser.parse(event['start']['date'])
          pickup_dates[block] = dt
      if block not in pickup_dates:
        logger.info('No pickup found for Block %s', block)

    #logger.info('pickup_date list' + json.dumps(pickup_dates))

    # Now we should have pickup dates for all blocks on job
    # Iterate through each msg and store pickup_date
    for block, date in pickup_dates.iteritems():
      logger.debug('Updating all %s with Next Pickup: %s', block, date)
      db['msgs'].update(
        {'job_id':job_id, 'imported.block':block}, 
        {'$set':{'next_pickup':date}},
        multi=True
      )
  
  except Exception, e:
    logger.error('get_next_pickups', exc_info=True)
    return str(e)

@celery_app.task
def send_receipts(entries, keys):
  try:
    url = 'http://www.bravoweb.ca/etap/etap_mongo.php'
    
    # Call eTap 'get_accounts' func for all accounts
    
    account_numbers = []

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

    for entry in entries:
      account_refs.append(entry['etap_account']['ref'])

    r = requests.post(url, data=json.dumps({
      "func": "get_gift_histories",
      "keys": keys,
      "data": {
        "account_refs": account_refs,
        "year": 2016 # FIXME
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
