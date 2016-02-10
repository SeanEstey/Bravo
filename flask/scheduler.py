import json
import requests
#import datetime
from dateutil.parser import parse
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
import re
from datetime import datetime,date, timedelta

from app import celery_app, db, logger, login_manager
from config import ETAP_WRAPPER_URL
from private_config import *
from gift_collections import create_rfu

def get_udf(field_name, etap_account):
  for field in etap_account['accountDefinedValues']:
    if field['fieldName'] == field_name:
      return field['value']

@celery_app.task
def find_nps_in_schedule(start=None, end=None):
  try:   
    # Default to 3 days in advance
    if start == None:
      start = datetime.now() + timedelta(days=3)
      end = start + timedelta(hours=12)

    json_key = json.load(open('oauth_credentials.json'))
    scope = ['https://www.googleapis.com/auth/calendar.readonly']
    credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)

    http = httplib2.Http()
    http = credentials.authorize(http)

    service = build('calendar', 'v3', http=http)
    events = service.events().list(
      calendarId = ETW_RES_CALENDAR_ID,
      timeMin = start.isoformat()+'+01:00',
      timeMax = end.isoformat()+'+01:00',
      singleEvents = True,
      orderBy = 'startTime'
    ).execute()

    logger.info('%i calendar events pulled', len(events['items']))

    for item in events['items']:
      res_block = re.match(r'^R([1-9]|10)[a-zA-Z]{1}', item['summary'])
      if res_block:
        res_block = res_block.group(0)
        
        r = requests.post(ETAP_WRAPPER_URL, data=json.dumps({
          "func": "get_query_accounts",
          "keys": ETAP_WRAPPER_KEYS,
          "data": {
            "query": res_block,
            "query_category": "ETW: Routes"
          }
        }))

        r = json.loads(r.text)
        
        analyze_non_participants(r['data'])

  except Exception, e:
    logger.error('find_nps_in_schedule', exc_info=True)
    return str(e)


def analyze_non_participants(etap_accounts):
  # Returns true if the account has been active for at least a year but
  # no contributions in past 12 months
  try:
    # Build list of accounts to query gift_histories for
    account_refs = []

    for account in etap_accounts:
      # Test if Dropoff Date was at least 12 months ago
      d = get_udf('Dropoff Date', account).split('/')
      dropoff_date = datetime(int(d[2]), int(d[1]), int(d[0])) 
      now = datetime.now()
      delta = now - dropoff_date

      if delta.days >= 365:
        account_refs.append(account['ref'])
      else:
        etap_accounts.remove(account)

    r = requests.post(ETAP_WRAPPER_URL, data=json.dumps({
      "func": "get_gift_histories",
      "keys": ETAP_WRAPPER_KEYS,
      "data": {
        "account_refs": account_refs,
        "start_date": str(now.day) + "/" + str(now.month) + "/" + str(now.year-1),
        "end_date": str(now.day) + "/" + str(now.month) + "/" + str(now.year)
      }
    }))
    
    gift_histories = json.loads(r.text)

    now = datetime.now()

    num_nps = 0

    for idx, gift_history in enumerate(gift_histories):
      account = etap_accounts[idx]

      if len(gift_history) == 0:
        num_nps += 1
        npu = get_udf('Next Pickup Date', account).split('/')

        next_pickup = npu[1] + '/' + npu[0] + '/' + npu[2]

        create_rfu(
          'Non-participant', 
          account_number = account['id'],
          next_pickup = next_pickup,
          block = get_udf('Block', account),
          date = str(now.month) + '/' + str(now.day) + '/' + str(now.year)
        )

    logger.info('Found ' + str(num_nps) + ' Non-Participants')

  except Exception, e:
    logger.error('analyze_non_participants', exc_info=True)
    return str(e)

@celery_app.task
def get_next_pickups(job_id):
  try:
    job_id = ObjectId(job_id)
    messages = db['msgs'].find({'job_id':job_id}, {'imported.block':1})
    blocks = []
    for msg in messages:
      if msg['imported']['block'] not in blocks:
        blocks.append(msg['imported']['block'])

    json_key = json.load(open('oauth_credentials.json'))
    scope = ['https://spreadsheets.google.com/feeds', 'https://docs.google.com/feeds']
    credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)

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

