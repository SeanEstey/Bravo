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
setLogger(logger, logging.DEBUG, 'log.log')

#-------------------------------------------------------------------
def dial(to):
  try:
    params = { 
        'from' : FROM_NUMBER,
        'caller_name': CALLER_ID,
        'to' : to,
        'answer_url' : URL+'/call/answer',
        'answer_method': 'POST',
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

    return response

  except Exception, e:
    logger.error('%s Call failed to dial (%a)',to, code, exc_info=True)
    return str(e)

#-------------------------------------------------------------------
def call_to_db(response, job_id, csv_row=None, db_record=None):
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
   
    response_code = str(response[0])
     
    # First call. Create new record.
    if csv_row is not None: 
        name = csv_row[0]
        date = csv_row[1]
        to = csv_row[2]
        call = {
          'job_id': job_id,
          'to': to,
          'name': name,
          'event_date': date,
          'attempts': 1
        }
        
        if response_code != '400':
            call['request_id'] = response[1]['request_uuid']
            call['status'] = response[1]['message']
            call['code'] = response_code
        
        db['calls'].insert(call)
    # Redial. Update record.
    elif db_record is not None:
        attempts = db_record['attempts'] + 1
        db['calls'].update(
            {'_id': db_record['_id']}, 
            {'$set': {
                'request_id': response[1]['request_uuid'],
                'status': response[1]['message'],
                'attempts': attempts
                }
            }
        )   

#-------------------------------------------------------------------
def send_email_report(job_id):
    logger.info('Sending report')

    import smtplib
    from email.mime.text import MIMEText

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    calls = list(db['calls'].find({'job_id':job_id},{'_id':0,'to':1,'status':1,'message':1}))
    calls_str = json.dumps(calls, sort_keys=True, indent=4, separators=(',',': ' ))
    
    msg = MIMEText(calls_str)

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
