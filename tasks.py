from config import *
from server import dial
from celery import Celery
from celery.signals import worker_process_init, task_prerun
import time
import os
from datetime import datetime,date
from secret import *
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
test_server_url = PUB_DOMAIN + ':' + str(PUB_TEST_PORT) + PREFIX 
mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
test_db = mongo_client[TEST_DB]

@celery_app.task
def run_scheduler():
  pending_jobs = test_db['jobs'].find({'status': 'pending'})
  print(str(pending_jobs.count()) + ' pending jobs:')

  job_num = 1
  for job in pending_jobs:
    if datetime.now() > job['fire_dtime']:
      logger.info('Starting scheduled Job [ID %s]', str(job['_id']))
      execute_job.delay(str(job['_id']), TEST_DB, test_server_url)
    else:
      next_job_delay = job['fire_dtime'] - datetime.now()
      print '{0}): {1} starts in {2}'.format(job_num, job['name'], str(next_job_delay))
    job_num += 1
  
  in_progress_jobs = test_db['jobs'].find({'status': 'in-progress'})
  print(str(in_progress_jobs.count()) + ' active jobs:')
  job_num = 1
  for job in in_progress_jobs:
    print('    ' + str(job_num) + '): ' + job['name'])

  return pending_jobs.count()

@celery_app.task
def execute_job(job_id, db_name, server_url):
  db = mongo_client[db_name]
  job_id = ObjectId(job_id)
  try:
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
    # Fire all calls
    for msg in messages:
      r = dial(msg['imported']['to'], server_url)
      if r['call_status'] == 'failed':
        logger.info('%s %s (%d: %s)', msg['imported']['to'], r['call_status'], r['error_code'], r['error_msg'])
      else: 
        logger.info('%s %s', msg['imported']['to'], r['call_status'])
      r['attempts'] = msg['attempts']+1
      db['msgs'].update(
        {'_id':msg['_id']},
        {'$set': r}
      )
      r['id'] = str(msg['_id'])
      payload = {'name': 'update_call', 'data': json.dumps(r)}
      requests.get(server_url + '/sendsocket', params=payload)
      #time.sleep(1)
    
    logger.info('Job Calls Fired. Monitoring...')

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
        requests.get(server_url + '/complete/' + str(job_id))
        
        return
      # Job still in progress. Any incomplete calls need redialing?
      elif actives.count() == 0 and incompletes.count() > 0:
        logger.info('Pausing %dsec then Re-attempting %d Incompletes.', REDIAL_DELAY, incompletes.count())
        time.sleep(REDIAL_DELAY)
        for call in incompletes:
          r = dial(call['imported']['to'], server_url)
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
    logger.error('execute_job job_id %s', str(job_id), exc_info=True)
