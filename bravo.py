from config import *
from celery import Celery
from celery.utils.log import get_task_logger
from bson.objectid import ObjectId
import plivo
import pymongo
import csv
import logging
import requests
import time
import json
from dateutil.parser import parse
from datetime import datetime,timedelta
import os

celery = Celery('tasks', cache='amqp', broker=BROKER_URI)
logger = logging.getLogger(__name__)
client = pymongo.MongoClient('localhost',27017)
db = client['wsf']

#-------------------------------------------------------------------
def setLogger(logger, level, log_name):
  handler = logging.FileHandler(log_name)
  handler.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  handler.setFormatter(formatter)

  logger.setLevel(level)
  logger.addHandler(handler)

setLogger(logger, logging.INFO, 'log.log')

#-------------------------------------------------------------------
def is_mongodb_available():
  if client:
    if client.alive():
      return True
  else:
    return False

#-------------------------------------------------------------------
def reconnect_mongodb():
  global client, db
  # Either no connection handle or connection is dead
  # Attempt to re-establish 
  logger.info('Attempting to reconnect to mongodb...')
  try:
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
  except pymongo.errors.ConnectionFailure as e:
    logger.error('mongodb connection refused!')
    return False

  return True

#-------------------------------------------------------------------
def is_server_online():
  try:
    response = requests.get(LOCAL_URL)
    if response.status_code == 200:
      return True
    else:
      return False
  except Exception, e:
    return False

#-------------------------------------------------------------------
def restart_server():
  logger.info('Attempting server restart...')
  os.system('python server.py &')
  time.sleep(5)
  if is_server_online() == False:
    sms(EMERGENCY_CONTACT, 'Bravo server offline! Cannot execute job!')
    return False

  logger.info('Successfully restarted. Resuming job...')
  return True

#-------------------------------------------------------------------
def is_celery_worker():
  if not celery.control.inspect().active_queues():
    return False
  else:
    return True

#-------------------------------------------------------------------
def restart_celery():
  # Attempt to restart celery worker
  logger.info('Attempting to restart celery worker...')
  try:
    os.system('./celery.sh &')
  except Exception as e:
    logger.error('Failed to restart celery worker')
    return False
  time.sleep(5)
  if not celery.control.inspect().active_queues():
    logger.error('Failed to restart celery worker')
    return False

  logger.info('Celery worker restarted')
  return True

#-------------------------------------------------------------------
def systems_check():
  if not is_celery_worker():
    #if not restart_celery():
      return False 
  if not is_server_online():
    return False
  #  if not restart_server():
  #    return False 
  if not is_mongodb_available():
    if not reconnect_mongodb():
      return False

  return True

#-------------------------------------------------------------------
@celery.task
def monitor_job(job_id):
  logger.info('Monitoring job %s' % str(job_id))

  while True:
    redial_query = {
      'job_id':job_id,
      'attempts': {'$lt': MAX_ATTEMPTS}, 
      '$or':[
        {'code':'USER_BUSY'},
        {'code':'NO_ANSWER'}
    ]}
    redials = db['msgs'].find(redial_query)
   
    # If no redials, test for job completion
    if redials.count() == 0:
      query_in_progress = {
        'job_id': job_id,
        '$or':[
          {'status': 'in-progress'},
          {'status': 'not-attempted'},
          {'status': 'ringing'},
          {'status': 'answered'}
      ]}
      in_progress = db['msgs'].find(query_in_progress)

      if in_progress.count() == 0:
        # Job Complete!
        db['jobs'].update(
          {'_id': job_id},
          {'$set': {'status': 'complete'}}
        )
       
        # Tell server to send completion sockets 
        completion_url = LOCAL_URL + '/complete/' + str(job_id)
        requests.get(completion_url)
        create_job_summary(job_id)
        send_email_report(job_id)
        break;
    # Redial calls as needed
    else:
      logger.info('Attempting redial ' + str(redials.count()) + ' calls')
      for redial in redials:
        fire_msg(redial)

    time.sleep(REDIAL_DELAY)

#-------------------------------------------------------------------
@celery.task
def execute_job(job_id):
  if isinstance(job_id, str):
    job_id = ObjectId(job_id)

  if not systems_check():
    msg = 'Could not execute job ' + str(job_id) + ' because systems are offline'
    send_email('estese@gmail.com', 'Bravo systems Offline!', msg)
    return False
 
  logger.info('\n********** Start Job ' + str(job_id) + ' **********')
  fire_msgs(job_id)
  time.sleep(60)
  monitor_job(job_id)
  logger.info('\n********** End Job ' + str(job_id) + ' **********\n')

#-------------------------------------------------------------------
# msg = mongodb json record
def fire_msg(msg):
  try:
    if not 'sms' in msg:
      # Voice Call
      response = dial(msg['to'])
      db['msgs'].update(
        {'_id': msg['_id']}, 
        {'$set': {
          'code': str(response[0]),
          'request_uuid': response[1]['request_uuid'],
          'status': response[1]['message'],
          'attempts': msg['attempts'] + 1
      }})
    else:
      # SMS
      job = db['jobs'].find_one({'_id':msg['job_id']})
      text = get_speak(job, msg, medium='sms')
      response = sms(msg['to'], text)
      res = db['msgs'].update(
        {'_id': msg['_id']},
        {'$set':{
          'message_uuid': response[1]['message_uuid'][0],
          'status': response[1]['message'],
          'code': response[1]['message'],
          'attempts': msg['attempts'] + 1,
          'speak': text
      }})
    
    code = str(response[0])
    # Endpoint probably overloaded
    if code == '400':
      logger.info('400 error in fire_msg. Taking a break...')
      time.sleep(10)

    # Cap at 1/sec for testing
    time.sleep(1)
  except Exception as e:
    logger.error('%s fire_msg.', exc_info=True)
    return str(e)

#-------------------------------------------------------------------
# job_id is the default _id field created for each jobs document by mongo
def fire_msgs(job_id):
  try:
    job = db['jobs'].find_one({'_id':job_id})
    # Default call order is alphabetically by name
    messages = db['msgs'].find({'job_id':job_id}).sort('name',1)

    if not messages:
      logger.info('No messages to fire for job_id ' + str(job_id) + '!')
      return False

    db['jobs'].update(
      {'_id': job['_id']},
      {'$set': {'status': 'in-progress'}}
    )

    # Fire all voice calls and SMS
    for msg in messages:
      fire_msg(msg)

    logger.info('All calls fired for job %s' % str(job_id))
    return True
  except Exception, e:
    logger.error('%s fire_msgs.', exc_info=True)
    return str(e)

#-------------------------------------------------------------------
# Run on fixed schedule from crontab, cycles through pending jobs
# and dispatches celery worker when due 
def check_job_schedule():
  if not systems_check():
    return False 

  pending_jobs = db['jobs'].find({'status': 'pending'})
  logger.info('Scheduler: ' + str(pending_jobs.count()) + ' pending jobs:')

  job_num = 1
  for job in pending_jobs:
    if datetime.now() > job['fire_dtime']:
      logger.info('Starting job %s' % str(job['_id']))
      execute_job.delay(job['_id'])
    else:
      next_job_delay = job['fire_dtime'] - datetime.now()
      logger.info(str(job_num) + '): ' + job['name'] + ' starts in: ' + str(next_job_delay))
    job_num += 1

  return True

#-------------------------------------------------------------------
def dial(to):
  if not to:
    return [
      'NO PHONE NUMBER', 
      {'request_uuid':'n/a', 'message': 'failed'}
    ]

  params = { 
    'from' : FROM_NUMBER,
    'caller_name': CALLER_ID,
    'to' : '+1' + to,
    'ring_url' :  PUB_URL+'/call/ring',
    'answer_url' : PUB_URL+'/call/answer',
    'answer_method': 'GET',
    'hangup_url': PUB_URL+'/call/hangup',
    'hangup_method': 'POST',
    'fallback_url': PUB_URL+'/call/fallback',
    'fallback_method': 'POST',
    'machine_detection': 'true',
    'machine_detection_url': PUB_URL+'/call/machine'
  }

  try:
    server = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    response = server.make_call(params)
  except Exception as e:
    logger.error('%s Bravo.dial() (%a)',to, code, exc_info=True)
    return [
      'PLIVO EXCEPTION', 
      {'request_uuid':'n/a', 'message': 'failed'}
    ]
  
  if type(response) == tuple:
    if 'request_uuid' not in response[1]:
      response[1]['request_uuid'] = 'n/a'
    if 'message' not in response[1]:
      response[1]['message'] = 'failed'

  # return tuple with format: (RESPONSE_CODE, {'request_uuid':ID, 'message':MSG})
  return response

#-------------------------------------------------------------------
def sms(to, msg):
  params = {
    'dst': '1' + to,
    'src': SMS_NUMBER,
    'text': msg,
    'type': 'sms',
    'url': PUB_URL + '/sms_status'
  }

  try:
    plivo_api = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    response = plivo_api.send_message(params)
    return response
  except Exception as e:
    logger.error('%s SMS failed (%a)',to, str(response[0]), exc_info=True)
    return False

#-------------------------------------------------------------------
def get_speak(job, msg, medium='voice', live=False):
  try:
    date_str = msg['event_date'].strftime('%A, %B %d')
  except TypeError:
    logger.error('Invalid date in get_speak: ' + str(msg['event_date']))
    return False

  intro_str = 'Hi, this is a friendly reminder that your empties to winn '
  repeat_voice = 'To repeat this message press 2. '
  no_pickup_voice = 'If you do not need a pickup, press 1. '
  no_pickup_sms = 'Reply with No if no pickup required.'
  speak = ''

  if job['template'] == 'etw_reminder':
    if msg['etw_status'] == 'Awaiting Dropoff':
      speak += (intro_str + 'dropoff date ' +
        'is ' + date_str + '. If you have any empties you can leave them ' +
        'out by 8am. ')
    elif msg['etw_status'] == 'Active':
      speak += (intro_str + 'pickup date ' +
        'is ' + date_str + '. please have your empties out by 8am. ')
      if medium == 'voice' and live == True:
        speak += no_pickup_voice
      elif medium == 'sms':
        speak += no_pickup_sms
    elif msg['etw_status'] == 'Cancelling':
      speak += (intro_str + 'bag stand will be picked up on ' +
        date_str + '. thanks for your past support. ')
    
    if medium == 'voice' and live == True:
      speak += repeat_voice
  elif job['template'] == 'special_msg':
    speak = job['message'] 
    print 'TODO'

  return speak

#-------------------------------------------------------------------
def strip_phone_num(to):
  return to.replace(' ', '').replace('(','').replace(')','').replace('-','')

#-------------------------------------------------------------------
def log_sms(record, response):
  db['msgs'].update(
    {'_id': record['_id']}, 
    {'$set': {
      'code': str(response[0]),
      'message_id': response[1]['message_uuid'],
      'status': response[1]['message'],
      'attempts': record['attempts']
      }
    }
  ) 

#-------------------------------------------------------------------
def create_job_summary(job_id):
  calls = list(db['msgs'].find({'job_id':job_id},{'_id':0}))
  job = {
    'summary': {
      'busy': 0,
      'no_answer': 0,
      'delivered': 0,
      'machine' : 0,
      'failed' : 0
    }
  }
  return True
'''
  for call in calls:
    if call['status'] == 'completed':
      if call['message'] == 'left voicemail':
        job['summary']['machine'] += 1
      elif call['message'] == 'delivered':
        job['summary']['delivered'] += 1
    elif call['status'] == 'busy':
      job['summary']['busy'] += 1
    elif call['status'] == 'failed':
      job['summary']['failed'] += 1
  db['jobs'].update(
    {'_id': job_id}, 
    {'$set': job}
  )
'''

#-------------------------------------------------------------------
def send_email_report(job_id):
  import smtplib
  from email.mime.text import MIMEText

  job = db['jobs'].find_one({'_id':job_id})
    
  calls = list(db['msgs'].find({'job_id':job_id},{'_id':0,'to':1,'status':1,'message':1}))
  calls_str = json.dumps(calls, sort_keys=True, indent=4, separators=(',',': ' ))
  sum_str = json.dumps(job['summary'])
  
  msg = sum_str + '\n\n' + calls_str
  subject = 'Job Summary %s' % str(job_id)

  send_email('estese@gmail.com', subject, msg)

#-------------------------------------------------------------------
def send_email(recipient, subject, msg):
  import requests
  send_url = 'https://api.mailgun.net/v2/' + MAILGUN_DOMAIN + '/messages'

  return requests.post(
    send_url,
    auth=('api', MAILGUN_API_KEY),
    data={
      'from': 'Empties to WINN <emptiestowinn@wsaf.ca>',
      'to': [recipient],
      'subject': subject,
      'text': msg
  })
