from config import *
from server_settings import *
from server import dial
from celery import Celery
from celery.signals import worker_process_init, task_prerun
import time
import os
from datetime import datetime,date
from bson.objectid import ObjectId
import pymongo
import twilio
from twilio import twiml
import logging
import requests
import json

logger = logging.getLogger(__name__)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(LOG_LEVEL)
handler.setFormatter(formatter)
logger.setLevel(LOG_LEVEL)
logger.addHandler(handler)
celery_app = Celery('tasks')
celery_app.config_from_object('config')
mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
db = mongo_client[DB_NAME]

@celery_app.task
def run_scheduler():
  pending_jobs = db['jobs'].find({'status': 'pending'})
  print(str(pending_jobs.count()) + ' pending jobs:')

  job_num = 1
  for job in pending_jobs:
    if datetime.now() > job['fire_dtime']:
      logger.info('Scheduler: Starting Job...')
      execute_job.apply_async((str(job['_id']), ), queue=DB_NAME)
    else:
      next_job_delay = job['fire_dtime'] - datetime.now()
      print '{0}): {1} starts in {2}'.format(job_num, job['name'], str(next_job_delay))
    job_num += 1
  
  in_progress_jobs = db['jobs'].find({'status': 'in-progress'})
  print(str(in_progress_jobs.count()) + ' active jobs:')
  job_num = 1
  for job in in_progress_jobs:
    print('    ' + str(job_num) + '): ' + job['name'])

  return pending_jobs.count()

@celery_app.task
def execute_job(job_id):
  try:
    job_id = ObjectId(job_id)
    job = db['jobs'].find_one({'_id':job_id})
    # Default call order is alphabetically by name
    messages = db['msgs'].find({'job_id':job_id}).sort('name',1)
    logger.info('\n\nStarting Job %s [ID %s]', job['name'], str(job_id))
    db['jobs'].update(
      {'_id': job['_id']},
      {'$set': {
        'status': 'in-progress',
        'started_at': datetime.now()
        }
      }
    )
    payload = {'name': 'update_job', 'data': json.dumps({'id':str(job['_id']), 'status':'in-progress'})}
    requests.get(LOCAL_URL+'/sendsocket', params=payload)
    # Fire all calls
    for msg in messages:
      if 'no_pickup' in msg:
        continue
      if msg['call_status'] != 'pending':
        continue
      r = dial(msg['imported']['to'])
      if r['call_status'] == 'failed':
        logger.info('%s %s (%d: %s)', msg['imported']['to'], r['call_status'], r['error_code'], r['call_error'])
      else: 
        logger.info('%s %s', msg['imported']['to'], r['call_status'])
      r['attempts'] = msg['attempts']+1
      db['msgs'].update(
        {'_id':msg['_id']},
        {'$set': r}
      )
      r['id'] = str(msg['_id'])
      payload = {'name': 'update_call', 'data': json.dumps(r)}
      requests.get(LOCAL_URL+'/sendsocket', params=payload)
    
    logger.info('Job Calls Fired.')
    r = requests.get(LOCAL_URL+'/fired/' + str(job_id))
    return 'OK'

  except Exception, e:
    logger.error('execute_job job_id %s', str(job_id), exc_info=True)

@celery_app.task
def monitor_job(job_id):
  try:
    logger.info('Tasks: Monitoring Job')
    job_id = ObjectId(job_id)
    job = db['jobs'].find_one({'_id':job_id})

    # Loop until no incomplete calls remaining (all either failed or complete)
    while True:
      # Any calls still active?
      actives = db['msgs'].find({
        'job_id': job_id,
        '$or':[
          {'call_status': 'queued'},
          {'call_status': 'ringing'},
          {'call_status': 'in-progress'}
        ]
      })
      # Any needing redial?
      incompletes = db['msgs'].find({
        'job_id':job_id,
        'attempts': {'$lt': MAX_ATTEMPTS}, 
        '$or':[
          {'call_status': 'busy'},
          {'call_status': 'no-answer'}
        ]
      })
      
      # Job Complete!
      if actives.count() == 0 and incompletes.count() == 0:
        db['jobs'].update(
          {'_id': job_id},
          {'$set': {
            'status': 'completed',
            'ended_at': datetime.now()
            }
        })
        logger.info('\nCompleted Job %s [ID %s]\n', job['name'], str(job_id))
        # Connect back to server and notify
        requests.get(PUB_URL + '/complete/' + str(job_id))
        
        return 'OK'
      # Job still in progress. Any incomplete calls need redialing?
      elif actives.count() == 0 and incompletes.count() > 0:
        logger.info('Pausing %dsec then Re-attempting %d Incompletes.', REDIAL_DELAY, incompletes.count())
        time.sleep(REDIAL_DELAY)
        for call in incompletes:
          r = dial(call['imported']['to'])
          logger.info('%s %s', call['imported']['to'], r['call_status'])
          r['attempts'] = call['attempts']+1
          db['msgs'].update(
            {'_id':call['_id']},
            {'$set': r}
          )
      # Still active calls going out  
      else:
        time.sleep(10)
    # End loop
    return 'OK'
  except Exception, e:
    logger.error('monitor_job job_id %s', str(job_id), exc_info=True)

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
      
    import httplib2
    from oauth2client.client import SignedJwtAssertionCredentials 
    from apiclient.discovery import build

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
          logger.info('Block %s Pickup Date: %s', block, event['start']['date'])
          pickup_dates[block] = event['start']['date']
      if block not in pickup_dates:
        logger.info('No pickup found for Block %s', block)

    logger.info('pickup_date list' + json.dumps(pickup_dates))

    # Now we should have pickup dates for all blocks on job
    # Iterate through each msg and store pickup_date
    for block, date in pickup_dates.iteritems():
      logger.info('Updating all %s with Next Pickup: %s', block, date)
      db['msgs'].update({'job_id':job_id, 'imported.block':block}, {'$set':{'next_pickup':date}})
  
  except Exception, e:
    logger.error('get_next_pickups', exc_info=True)
    return str(e)
