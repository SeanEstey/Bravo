from config import *
from secret import *
from celery import Celery
from celery.utils.log import get_task_logger
from bson.objectid import ObjectId
import twilio
import pymongo
import csv
import logging
import requests
import time
import json
from dateutil.parser import parse
from datetime import datetime,timedelta
import os

celery = Celery(CELERY_MODULE, cache='amqp', broker=BROKER_URI)
local_url = None
pub_url = None
client = None
db = None
logger = logging.getLogger(__name__)

def set_mode(mode):
  global client, db, logger, pub_url, local_url
  client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)

  if mode == 'test':
    db = client[TEST_DB]
    local_url = 'http://localhost:'+str(LOCAL_TEST_PORT)
    pub_url = PUB_DOMAIN + ':' + str(PUB_TEST_PORT) + PREFIX 
  elif mode == 'deploy':
    db = client[DEPLOY_DB]
    local_url = 'http://localhost:'+str(LOCAL_DEPLOY_PORT)
    pub_url = PUB_DOMAIN + PREFIX

  set_logger(logger, LOG_LEVEL, LOG_FILE)

def set_logger(logger, level, log_name):
  handler = logging.FileHandler(log_name)
  handler.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  handler.setFormatter(formatter)
  logger.setLevel(level)
  logger.handlers = []
  logger.addHandler(handler)

def is_mongodb_available():
  if client:
    if client.alive():
      return True
  else:
    return False

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

def is_server_online():
  try:
    response = requests.get(local_url)
    if response.status_code == 200:
      return True
    else:
      return False
  except Exception, e:
    return False

def restart_server():
  logger.info('Attempting server restart...')
  os.system('python server.py &')
  time.sleep(5)
  if is_server_online() == False:
    sms(EMERGENCY_CONTACT, 'Bravo server offline! Cannot execute job!')
    return False

  logger.info('Successfully restarted. Resuming job...')
  return True

def is_celery_worker():
  if not celery.control.inspect().active_queues():
    return False
  else:
    return True

def restart_celery():
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

@celery.task
def monitor_job(job_id):
  logger.info('Monitoring job %s' % str(job_id))
  try:
    while True:
      # Any active msg's?
      if db['msgs'].find({
        'job_id': job_id,
        '$or':[
          {'status': 'IN_PROGRESS'},
          {'status': 'PENDING'}
        ]
      }).count() == 0:
        # Job Complete!
        db['jobs'].update(
          {'_id': job_id},
          {'$set': {
            'status': 'COMPLETE',
            'ended_at': datetime.now()
            }
        })
        create_job_summary(job_id)
        completion_url = local_url + '/complete/' + str(job_id)
        requests.get(completion_url)
        #send_email_report(job_id)
        return
      # Job still in progress. Any incomplete calls need redialing?
      else:
        redials = db['msgs'].find({
          'job_id':job_id,
          'attempts': {'$lt': MAX_ATTEMPTS}, 
          '$or':[
            {'code': 'NO_ENDPOINT'},
            {'code': 'USER_BUSY'},
            {'code': 'NO_ANSWER'}
          ]
        })
        if redials.count() > 0:
          logger.info(str(redials.count()) + ' calls incomplete. Pausing for ' + str(REDIAL_DELAY) + 's then redialing...')
          time.sleep(REDIAL_DELAY)
          for redial in redials:
            fire_msg(redial)
        else:
          time.sleep(10)
      # End loop
  except Exception, e:
    logger.error('monitor_job job_id %s', str(job_id), exc_info=True)
    return str(e)

@celery.task
def execute_job(job_id):
  try:
    if isinstance(job_id, str):
      job_id = ObjectId(job_id)

    if not systems_check():
      msg = 'Systems check failed during execution of job_id ' + str(job_id)
      #send_email('estese@gmail.com', 'Bravo systems Offline!', msg)
      logger.error(msg)
      return False
  
    job = db['jobs'].find_one({'_id':job_id})
    # Default call order is alphabetically by name
    messages = db['msgs'].find({'job_id':job_id}).sort('name',1)

    if not messages:
      logger.error('No msgs in job_id ' + str(job_id))
      return False

    logger.info('\n\n********** Start Job ' + str(job_id) + ' **********')
    
    db['jobs'].update(
      {'_id': job['_id']},
      {'$set': {
        'status': 'IN_PROGRESS',
        'started_at': datetime.now()
        }
      }
    )
  except Exception, e:
    logger.error('execute_job job_id %s', str(job_id), exc_info=True)
    return str(e)

  # Fire all voice calls and SMS
  for msg in messages:
    fire_msg(msg)
    # Cap at 1/sec for testing
    time.sleep(1)

  logger.info('All calls fired for job %s. Sleeping 60s...', str(job_id))
  time.sleep(60)
  monitor_job(job_id)
  logger.info('\n********** End Job ' + str(job_id) + ' **********\n\n')
  return True

# message_uuid: primary msg ID for SMS returned in Plivo response
# sid: primary msg ID for Voice returned in Plivo response
def fire_msg(msg):
  fields = {}
  try:
    # Voice Call
    if not 'sms' in msg:
      response = dial(msg['imported']['to'])
      # Status Code on success = 201
      if response[0] != 400:
        fields['sid'] = response[1]['sid']
        fields['attempts'] = msg['attempts'] + 1
        fields['call_status'] = response[1]['call_status']
    # SMS
    else:
      job = db['jobs'].find_one({'_id':msg['job_id']})
      text = get_speak(job, msg, medium='sms')
      response = sms(msg['imported']['to'], text)
      # Status Code on success = 202
      if response[0] != 400:
        fields['sid'] = response[1]['sid'][0]
        fields['attempts'] = msg['attempts'] + 1
        fields['status'] = 'IN_PROGRESS'
        fields['call_status'] = response[1]['call_status']
        fields['speak'] = text
    
    status_code = response[0]
    logger.debug('fire_msg response: ' + json.dumps(response))
    
    if status_code == 400:
        fields['call_status'] = 'failed'
        fields['sid'] = ''

    logger.info('%s %s', msg['imported']['to'], fields['call_status'])

    db['msgs'].update(
      {'_id': msg['_id']}, 
      {'$set': fields})

    return response
  except Exception as e:
    logger.error('%s fire_msg.', exc_info=True)
    return str(e)

# Run on fixed schedule from crontab, cycles through pending jobs
# and dispatches celery worker when due 
def run_scheduler():
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

# Plivo returns 'sid' on successful dial attempt. This will 
# be the primary ID in db['msgs']
def dial(to):
  # TWILIO API
  if not to:
    return [400, {'sid':'', 'message': 'NO_PHONE_NUMBER'}]

  try:
    client = twilio.rest.TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_ID)
    call = client.calls.create(
      from_=TWILIO_NUMBER,
      to='+1'+to,
      url=pub_url + '/call/answer',
      status_callback=pub_url + '/call/status',
      status_method='POST',
      method='POST',
      if_machine='Continue'
    )
      
  except Exception as e:
    logger.error('twilio.call exception: ', exc_info=True)
    return [400, {'sid':'', 'call_status': 'failed'}]
 
  return [200, {'sid':call.sid, 'call_status':call.status}]
  # return tuple with format: (RESPONSE_CODE, {'sid':ID, 'message':MSG})

# Plivo returns 'sid' on successful sms attempt. This will 
# be the primary ID in db['msgs']
def sms(to, msg):
  params = {
    'dst': '1' + to,
    'src': SMS_NUMBER,
    'text': msg,
    'type': 'sms',
    'url': pub_url + '/sms_status'
  }

  try:
    plivo_api = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    response = plivo_api.send_message(params)
    return response
  except Exception as e:
    logger.error('%s SMS failed (%a)',to, str(response[0]), exc_info=True)
    return False

def get_speak(job, msg, medium='voice', live=False):
  try:
    date_str = msg['imported']['event_date'].strftime('%A, %B %d')
  except TypeError:
    logger.error('Invalid date in get_speak: ' + str(msg['imported']['event_date']))
    return False

  intro_str = 'Hi, this is a friendly reminder that your empties to winn '
  repeat_voice = 'To repeat this message press 2. '
  no_pickup_voice = 'If you do not need a pickup, press 1. '
  no_pickup_sms = 'Reply with No if no pickup required.'
  speak = ''

  if job['template'] == 'etw_reminder':
    if msg['imported']['status'] == 'Dropoff':
      speak += (intro_str + 'dropoff date ' +
        'is ' + date_str + '. If you have any empties you can leave them ' +
        'out by 8am. ')
    elif msg['imported']['status'] == 'Active':
      speak += (intro_str + 'pickup date ' +
        'is ' + date_str + '. please have your empties out by 8am. ')
      if medium == 'voice' and live == True:
        speak += no_pickup_voice
      elif medium == 'sms':
        speak += no_pickup_sms
    elif msg['imported']['status'] == 'Cancelling':
      speak += (intro_str + 'bag stand will be picked up on ' +
        date_str + '. thanks for your past support. ')
    
    if medium == 'voice' and live == True:
      speak += repeat_voice
  elif job['template'] == 'gg_delivery':
    speak = ('Hi, this is friendly reminder that your green goods delivery will be on ' +
      date_str + '. Your order total is ' + msg['imported']['price'] + '. ')
    if medium == 'voice' and live == True:
      speak += repeat_voice
  elif job['template'] == 'special_msg':
    speak = job['speak'] 

  return speak

def strip_phone_num(to):
  return to.replace(' ', '').replace('(','').replace(')','').replace('-','')

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

def create_job_summary(job_id):
  if isinstance(job_id, str):
    job_id = ObjectId(job_id)

  calls = db['msgs'].find({'job_id':job_id},{'_id':0})
  
  summary = {
    'totals': {
      'completed': 0,
      'no_answer' : 0,
      'busy': 0,
      'failed' : 0
    },
    'calls': {}
  }

  for call in calls:
    if call['call_status'] == 'completed':
      summary['totals']['completed'] += 1
    elif call['call_status'] == 'no_answer':
      summary['totals']['no_answer'] += 1
    elif call['call_status'] == 'busy':
      summary['totals']['busy'] += 1
    elif call['call_status'] == 'failed':
      summary['totals']['failed'] += 1

    summary['calls'][call['imported']['name']] = {
      'phone': call['imported']['to'],
      'call_status': call['call_status'],
      'attempts': call['attempts'],
    }

    if 'sid' in call:
      summary['calls'][call['imported']['name']]['sid'] = call['sid']
    if 'answered_by' in call:
      summary['calls'][call['imported']['name']]['answered_by'] = call['answered_by']
  
  job = db['jobs'].find_one({'_id':job_id})

  delta = job['ended_at'] - job['started_at']
  
  summary['elapsed'] = delta.total_seconds()

  return json.dumps(summary)

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
