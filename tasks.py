from config import *
from server import mongo_client, logger, dial
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

celery_app = Celery()
celery_app.config_from_object('config')
test_server_url = PUB_DOMAIN + ':' + str(PUB_TEST_PORT) + PREFIX 
test_db = mongo_client[TEST_DB]

@celery_app.task
def run_scheduler():
  pending_jobs = test_db['jobs'].find({'status': 'pending'})
  print('Scheduler: ' + str(pending_jobs.count()) + ' pending jobs:')

  job_num = 1
  for job in pending_jobs:
    if datetime.now() > job['fire_dtime']:
      logger.info('Starting job %s' % str(job['_id']))
      execute_job.delay(job['_id'], TEST_DB, test_server_url)
    else:
      next_job_delay = job['fire_dtime'] - datetime.now()
      print(str(job_num) + '): ' + job['name'] + ' starts in: ' + str(next_job_delay))
    job_num += 1
  return True

@celery_app.task
def execute_job(job_id, db_name, server_url):
  db = mongo_client[db_name]
  #if type(job_id) == str:
  #  logger.info('converting str id to bson objectid')
  job_id = ObjectId(job_id)
  logger.info('execute job: os.environ[title]='+str(os.environ['title']))
  try:
    job = db['jobs'].find_one({'_id':job_id})
    # Default call order is alphabetically by name
    messages = db['msgs'].find({'job_id':job_id}).sort('name',1)
    logger.info('\n\n********** Start Job ' + str(job_id) + ' **********')
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
      response = dial(msg['imported']['to'], server_url)
      logger.info('%s %s', msg['imported']['to'], response['call_status'])
      response['attempts'] = msg['attempts']+1
      db['msgs'].update(
        {'_id':msg['_id']},
        {'$set': response}
      )
      response['id'] = str(msg['_id'])
      #send_socket('update_call', response)
      time.sleep(1)
    monitor_job(job_id, db, server_url)
    logger.info('\n********** End Job ' + str(job_id) + ' **********\n\n')
  except Exception, e:
    logger.error('execute_job job_id %s', str(job_id), exc_info=True)

def monitor_job(job_id, db, server_url):
  logger.info('Monitoring job %s' % str(job_id))
  try:
    while True:
      # Any calls still active?
      active = db['msgs'].find({
        'job_id': job_id,
        '$or':[
          {'call_status': 'queued'},
          {'call_status': 'ringing'},
          {'call_status': 'in-progress'}
        ]
      })
      # Any needing redial?
      incomplete = db['msgs'].find({
        'job_id':job_id,
        'attempts': {'$lt': MAX_ATTEMPTS}, 
        '$or':[
          {'call_status': 'busy'},
          {'call_status': 'no-answer'}
        ]
      })
      
      # Job Complete!
      if active.count() == 0 and incomplete.count() == 0:
        db['jobs'].update(
          {'_id': job_id},
          {'$set': {
            'status': 'completed',
            'ended_at': datetime.now()
            }
        })
        #create_job_summary(job_id)
        #job_complete(str(job_id))
        #completion_url = os.environ['local_url'] + '/complete/' + str(job_id)
        #requests.get(completion_url)
        #send_email_report(job_id)
        return
      # Job still in progress. Any incomplete calls need redialing?
      elif active.count() == 0 and incomplete.count() > 0:
        logger.info(str(redials.count()) + ' calls incomplete. Pausing for ' + str(REDIAL_DELAY) + 's then redialing...')
        time.sleep(REDIAL_DELAY)
        for redial in redials:
          response = dial(redial['imported']['to'], server_url)
          logger.info('%s %s', msg['imported']['to'], response['call_status'])
          response['attempts'] = msg['attempts']+1
          db['msgs'].update(
            {'_id':msg['_id']},
            {'$set': response}
          )
      # Still active calls going out  
      else:
        time.sleep(10)
    # End loop
  except Exception, e:
    logger.error('monitor_job job_id %s', str(job_id), exc_info=True)
    return str(e)

