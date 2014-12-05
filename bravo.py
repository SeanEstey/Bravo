from config import *
from bson.objectid import ObjectId
import plivo
import pymongo
import urllib2
import csv
import logging
import time
import json

logger = logging.getLogger(__name__)
setLogger(logger, logging.INFO, 'log.log')

#-------------------------------------------------------------------
def dial(to):
  try:
    params = { 
      'from' : FROM_NUMBER,
      'caller_name': CALLER_ID,
      'to' : '+1' + to,
      'ring_url' :  URL+'/call/ring',
      'answer_url' : URL+'/call/answer',
      'answer_method': 'GET',
      'hangup_url': URL+'/call/hangup',
      'hangup_method': 'POST',
      'fallback_url': URL+'/call/fallback',
      'fallback_method': 'POST',
      'machine_detection': 'true',
      'machine_detection_url': URL+'/call/machine'
    }

    server = plivo.RestAPI(AUTH_ID, AUTH_TOKEN)
    response = server.make_call(params)
    code = str(response[0])
    if code != '400':
        logger.info('%s %s (%s)', to, response[1]['message'], response[0])
    else:
        logger.info('%s: 400 error' % to)

    if type(response) == tuple:
      if 'request_uuid' not in response[1]:
        response[1]['request_uuid'] = 'n/a'
      
      if 'message' not in response[1]:
        response[1]['message'] = 'failed'

    # return tuple with format: (RESPONSE_CODE, {'request_uuid':ID, 'message':MSG})
    return response

  except Exception, e:
    logger.error('%s Call failed to dial (%a)',to, code, exc_info=True)
    return str(e)

#-------------------------------------------------------------------
def getSpeak(template, etw_status, date_str):
  intro_str = 'Hi, this is a friendly reminder from the Winny Fred stewart association '
  repeat_str = 'To repeat this message press 1. '
  no_pickup_str = 'If you do not need a pickup, press 2. '

  if template == 'etw_reminder':
    if etw_status == 'Awaiting Dropoff':
      speak = (intro_str + 'that your empties to winn dropoff date ' +
        'is ' + date_str + '. If you have any empties you can leave them ' +
        'out by 8am. ' + repeat_str
      )
    elif etw_status == 'Active':
      speak = (intro_str + 'that your next empties to winn pickup date ' +
        'is ' + date_str + '. please have your empties out by 8am. ' + 
        repeat_str + no_pickup_str
      )
    elif etw_status == 'Cancelling':
      speak = (intro_str + 'that we will come by to pick up your bag stand ' +
        'on ' + date_str + '. thanks for your past support. ' + repeat_str
      )
    else:
      speak = ''
  elif template == 'special_msg':
    print 'TODO'
  elif template == 'etw_welcome':
    print 'TODO'
  elif template == 'gg_delivery':
    print 'TODO'

  return speak

#-------------------------------------------------------------------
# Add request_uuid, call_uuid and code to mongo record
# Update status and attempts
# response format: (code, {message: val, request_uuid: val})
def update(call, response):
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
 
  if response[1]['message'] != 'call fired':
    call['attempts'] += 1
  
  db['calls'].update(
    {'_id': call['_id']}, 
    {'$set': {
      'code': str(response[0]),
      'request_id': response[1]['request_uuid'],
      'status': response[1]['message'],
      'attempts': call['attempts']
      }
    }
  ) 

#-------------------------------------------------------------------
def create_job_summary(job_id):
  logger.info('Creating job summary for %s' % job_id)

  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  calls = list(db['calls'].find({'job_id':job_id},{'_id':0}))

  job = {
    'summary': {
      'busy': 0,
      'no_answer': 0,
      'delivered': 0,
      'machine' : 0,
      'failed' : 0
    }
  }

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

  #logger.info('Summary for job %s:\ndelivered: %s\nmachine: %s\nbusy: %s\nfailed: %s', job_id, str(delivered), str(machine), str(busy), str(failed))

  db['jobs'].update(
    {'_id': ObjectId(job_id)}, 
    {'$set': job}
  )

  logger.info('done')


#-------------------------------------------------------------------
def send_email_report(job_id):
  logger.info('Sending report')

  import smtplib
  from email.mime.text import MIMEText

  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  job = db['jobs'].find_one({'_id':ObjectId(job_id)})
    
  calls = list(db['calls'].find({'job_id':job_id},{'_id':0,'to':1,'status':1,'message':1}))
  calls_str = json.dumps(calls, sort_keys=True, indent=4, separators=(',',': ' ))
  sum_str = json.dumps(job['summary'])
  
  msg = MIMEText(sum_str + '\n\n' + calls_str)

  username = 'winnstew'
  password = 'batman()'
  me = 'winnstew@gmail.com'
  you = 'estese@gmail.com'

  msg['Subject'] = 'Job Summary %s' % job_id
  msg['From'] = me
  msg['To'] = you

  s = smtplib.SMTP('smtp.gmail.com:587')
  s.ehlo()
  s.starttls()
  s.login(username, password)
  s.sendmail(me, [you], msg.as_string())
  s.quit()
