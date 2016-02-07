import json
import requests
import datetime
from dateutil.parser import parse

from app import celery_app, db, logger, login_manager
from server_settings import PHP_KEYS


def get_udf_from_etap_account(field_name, udf):
    for field in udf:
        if field['fieldName'] == field_name:
            return field['value']

def is_non_participant(account_number):
  try:
    url = 'http://www.bravoweb.ca/etap/etap_mongo.php'
    logger.info('querying gift history for ' + account_number)
    
    r = requests.post(url, data=json.dumps({
      "func": "get_accounts",
      "keys": PHP_KEYS,
      "data": {
        "account_numbers": [account_number]
      }
    }))

    account = json.loads(r.text)[0]

    now = datetime.datetime.now()

    # TODO: Test if Dropoff Date was at least 12 months ago

    dropoff_date = parse(get_udf_from_etap_account('Dropoff Date', account['accountDefinedValues']))

    delta = now - dropoff_date

    if delta.days < 365:
        logger.info('Not eligible to be non-participant. Dropoff < 1 year ago')
        return 'ok'

    r = requests.post(url, data=json.dumps({
      "func": "get_gift_histories",
      "keys": PHP_KEYS,
      "data": {
        "account_refs": [account['ref']],
        "start_date": str(now.day) + "/" + str(now.month) + "/" + str(now.year-1),
        "end_date": str(now.day) + "/" + str(now.month) + "/" + str(now.year)
      }
    }))
    
    gifts = json.loads(r.text)[0]

    for gift in gifts:
      if gift.amount > 0:
        return "Active Participant!"

    logger.info('Non-participant!')
    return "Non-participant!"

  except Exception, e:
    logger.error('is_non_participant', exc_info=True)
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

