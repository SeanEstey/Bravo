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
    params = { 
        'from' : FROM_NUMBER,
        'caller_name': CALLER_ID,
        'to' : to,
        'answer_url' : URL+'/call/answer',
        'answer_method': 'POST',
        'hangup_url': URL+'/call/hangup',
        'hangup_method': 'POST',
        'machine_detection': 'true',
        'machine_detection_url': URL+'/call/machine'
    }

    server = plivo.RestAPI(AUTH_ID, AUTH_TOKEN)
    response = server.make_call(params)
    logger.info('%s %s (%s)', to, response[1]['message'], response[0])
    return response

#-------------------------------------------------------------------
def call_to_db(response, job_id, csv_row=None, db_record=None):
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    
    # First call. Create new record.
    if csv_row is not None: 
        name = csv_row[0]
        date = csv_row[1]
        to = csv_row[2]
        call = {
          'request_id': response[1]['request_uuid'],
          'job_id': job_id,
          'to': to,
          'status': response[1]['message'],
          'name': name,
          'event_date': date,
          'attempts': 1
        }
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
def monitor_bulk_call(job_id):
    logger.info('Monitoring job %s' % job_id)

    time.sleep(60)

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']

    while True:
        redials = {
            'job_id':job_id,
            'attempts': {'$lt': MAX_ATTEMPTS}, 
            '$or':[
                {'status':'busy'},
                {'status':'no answer'}
            ]
        }
        cursor = db['calls'].find(redials)
        
        if cursor.count() == 0:
            logger.info('job %s complete' % job_id)
            break;
            #continue;
        else:
            for each in cursor:
                print each['status']
                # Redial
                response = dial(each['to'])
                call_to_db(response, job_id, db_record=each)
        time.sleep(60)

#-------------------------------------------------------------------
def send_email_report(job_id):
    logger.info('Sending report')

    import smtplib
    from email.mime.text import MIMEText

    textfile = 'email_file.txt'
    # Open a plain text file for reading.  For this example, assume that
    # the text file contains only ASCII characters.
    fp = open(textfile, 'rb')
    # Create a text/plain message
    msg = MIMEText(fp.read())
    fp.close()

    username = 'winnstew'
    password = 'batman()'
    me = 'winnstew@gmail.com'
    you = 'estese@gmail.com'

    msg['Subject'] = 'The contents of %s' % textfile
    msg['From'] = me
    msg['To'] = you

    s = smtplib.SMTP('smtp.gmail.com:587')
    s.ehlo()
    s.starttls()
    s.login(username, password)
    s.sendmail(me, [you], msg.as_string())
    s.quit()
