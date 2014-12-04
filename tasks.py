from celery import Celery
from celery.utils.log import get_task_logger
from config import *
from bson.objectid import ObjectId
import plivo
import pymongo
import urllib2
import csv
import logging
import time
import json
import bravo
import server
from datetime import datetime,timedelta

celery = Celery('tasks', cache='amqp', broker=BROKER_URI)
logger = get_task_logger(__name__)
setLogger(logger, logging.INFO, 'log.log')

#-------------------------------------------------------------------
# Checks every 30 seconds for any pending jobs to fire.
# Dispatches celery worker for each
def schedule_jobs():
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']

  while True:
    pending_jobs = db['jobs'].find({'status': 'pending'})
    print str(pending_jobs.count()) + ' pending jobs:'
    i=1

    for job in pending_jobs:
      if datetime.now() > job['fire_dtime']:
        print 'starting job %s' % str(job['_id'])
        logger.info('Starting job %s' % str(job['_id']))
        execute_job.delay(str(job['_id']))
      else:
        next_job_delay = job['fire_dtime'] - datetime.now()
        print str(i) + '): starts in: ' + str(next_job_delay)
      i+=1

    time.sleep(60)

#-------------------------------------------------------------------
@celery.task
def monitor_job(job_id):
  logger.info('Monitoring job %s' % job_id)

  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']

  while True:
    redial_query = {
      'job_id':job_id,
      'attempts': {'$lt': MAX_ATTEMPTS}, 
      '$or':[
        {'status':'busy'},
        {'status':'no answer'}
      ]
    }
    redials = db['calls'].find(redial_query)
   
    # If no redials, test for job completion
    if redials.count() == 0:
      query_in_progress = {
        'job_id': job_id,
        'status': 'call fired'
      }
      in_progress = db['calls'].find(query_in_progress)

      if in_progress.count() == 0:
        logger.info('job %s complete' % job_id)
        db['jobs'].update(
          {'_id': ObjectId(job_id)},
          {'$set': {'status': 'complete'}}
        )
        bravo.create_job_summary(job_id)
        bravo.send_email_report(job_id)
        break;
    # Redial calls as needed
    else:
      for redial in redials:
        print redial['status']
        response = bravo.dial(redial['to'])
        bravo.update(redial, response)
    time.sleep(60)

#-------------------------------------------------------------------
@celery.task
def execute_job(job_id):
  fire_calls(job_id)
  time.sleep(60)
  monitor_job(job_id)

#-------------------------------------------------------------------
# job_id is the default _id field created for each jobs document by mongo
@celery.task
def fire_calls(job_id):
  logger.info('Firing calls for job %s' % job_id)

  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  job = db['jobs'].find_one({'_id':ObjectId(job_id)})
  calls = db['calls'].find({'job_id':job_id})

  db['jobs'].update(
    {'_id': job['_id']},
    {'$set': {'status': 'in_progress'}}
  )

  # Dial the calls
  for call in calls:
    response = bravo.dial(call['to'])
    bravo.update(call, response)
    
    code = str(response[0])
    # Endpoint probably overloaded
    if code == '400':
        print 'taking a break...'
        time.sleep(10)

    time.sleep(1)

  logger.info('All calls fired for job %s' % job_id)

#-------------------------------------------------------------------
@celery.task
def validate_job(job_id):
    '''fire the validation and thus fire the calls'''
    print "Validating: ", job_id

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    data = db['calls'].find_one({'request_id':job_id})

    print "Got data:", data['from_number']

    params = {
        'from' : FROM_NUMBER,
        'caller_name': CALLER_ID,
        'to'   : data['from_number'],
        'answer_url' : URL+'/verify/'+job_id
    }

    print "Params are: ", params

    p = plivo.RestAPI(data['auth_id'],data['auth_token'])
    resp = p.make_call(params)
    print "Fired: ", resp
