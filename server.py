from flask import Flask,render_template,request,g,Response
from config import *
from bson.objectid import ObjectId
import pymongo
import plivo
import plivoxml
from datetime import datetime,date
from dateutil.parser import parse
import os
import time
import tasks
import urllib2
import csv
import logging

logger = logging.getLogger(__name__)
setLogger(logger, logging.INFO, 'log.log')

app = Flask(__name__)
app.config.from_pyfile('config.py')

#-------------------------------------------------------------------
def push_data(verify_phone, message, audio_url, audio_order, csv_url, fire_dtime):
    record = {
        'auth_id': AUTH_ID,
        'auth_token': AUTH_TOKEN,
        'cps': CPS,
        'max_attempts': MAX_ATTEMPTS,
        'verify_phone': verify_phone,
        'message': message,
        'audio_url': audio_url,
        'audio_order': audio_order,
        'csv_url': csv_url,
        'fire_dtime': fire_dtime,
        'status': True
    }

    job_id = db['call_jobs'].insert(record)
    return job_id

#-------------------------------------------------------------------
@app.route('/')
def index():
    logger.info('test init')
    return render_template('user_input.html')

#-------------------------------------------------------------------
@app.route('/input', methods=['POST'])
def input():
    if request.method == 'POST':
        date_string = request.form['date']+' '+request.form['time']
        fire_dtime = parse(date_string)

        if request.form['order'] == 'after':
            order = False
        else:
            order = True

        job_id = push_data(
            request.form['verify_phone'],
            request.form['message'],
            request.form['audio'],
            order, 
            request.form['csv'],
            fire_dtime
        )

        logger.info('Job %s added to DB' % job_id)
        return "Got Data: Messge id is %s" % job_id

#-------------------------------------------------------------------
@app.route('/call/answer',methods=['POST','GET'])
def content():
  try:
    logger.debug('Call answered %s' % request.values.items())

    if request.form.get('Direction') == 'inbound':
      response = plivoxml.Response()
      return Response(str(response), mimetype='text/xml')

    request_uuid = request.form.get('RequestUUID')
    call_uuid = request.form.get('CallUUID')
    
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set':{
            'status': 'answered',
            'message': 'delivered', 
            'call_uuid': call_uuid
            }}
    )
    call = db['calls'].find_one({'request_id':request_uuid})
    dt = parse(call['event_date'])
    date_str = dt.strftime('%A, %B %d')
    speak = ('Hi, this is a friendly reminder from the Winny Fred ' +
      'stewart association that your next empties to winn pickup date ' +
      'is ' + date_str + '. please have your empties out by 8am. ' +
      'To repeat this message press 1.'
    )
  
    logger.debug('%s Answered.' % call['to'])
   
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addSpeak(body=speak)
    return Response(str(response), mimetype='text/xml')
  
  except Exception, e:
    logger.error('%s answered. Failed to update DB or deliver message' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/hangup',methods=['POST','GET'])
def process_hangup():
  try:
    call_status = request.form.get('CallStatus')
    to = request.form.get('To')
    cause = request.form.get('HangupCause')
    request_uuid = request.form.get('RequestUUID')
    
    logger.info('%s %s (%s) /call/hangup', to, call_status, cause)
    logger.debug('Call hungup %s' % request.values.items())

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']

    call = db['calls'].find_one({'request_id':request_uuid})
    attempts = int(call['attempts'])

    if call_status != 'failed':
      attempts += 1

    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set': {
            'status': call_status,
            'code': cause,
            'attempts': attempts
            }
        }
    )

    response = plivoxml.Response()
    return Response(str(response), mimetype='text/xml')
  
  except Exception, e:
    logger.error('%s Failed to process hangup' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/fallback',methods=['POST','GET'])
def process_fallback():
  try:
    post_data = str(request.form.values())
    print post_data
    logger.info('call fallback data: %s' % post_data)
    response = plivoxml.Response()
    return Response(str(response), mimetype='text/xml')
  except Exception, e:
    logger.error('%s Failed to process fallback' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/machine',methods=['POST','GET'])
def process_machine():
  try:
    to = request.form.get('To', None)
    request_uuid = request.form.get('RequestUUID')
    call_uuid = request.form.get('CallUUID')

    logger.debug('Machine detected. Transferring to voicemail. %s' % request.values.items())

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set': {'status':'machine'}}
    )
    
    server = plivo.RestAPI(AUTH_ID, AUTH_TOKEN)
    params = {
        'call_uuid': call_uuid,
        'legs': 'aleg',
        'aleg_url' : URL+'/call/voicemail',
        'aleg_method': 'POST',
    }
    resp  = server.transfer_call(params)

    # response = plivoxml.Response()
    return Response(str(resp), mimetype='text/xml')
  
  except Exception, e:
    logger.error('%s Failed to process machine detection' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/voicemail',methods=['POST','GET'])
def process_voicemail():
  try:
    logger.debug('Call routed to leave voicemail. %s' % request.values.items())

    request_uuid = request.form.get('RequestUUID')
    
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set': {
            'status':'voicemail',
            'message': 'left voicemail'
            }}
    )
    call = db['calls'].find_one({'request_id':request_uuid})
    dt = parse(call['event_date'])
    date_str = dt.strftime('%A, %B %d')
    speak = 'Hi, this is a friendly reminder from the winny fred stewart association that your next empties to winn pickup date is ' + date_str
   
    logger.info('%s Leaving voicemail.' % call['to'])
    
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addSpeak(body=speak)
    return Response(str(response), mimetype='text/xml')
  
  except Exception, e:
    logger.error('%s Failed to leave voicemail' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/verify/<job_id>', methods = ['POST', 'GET'])
def verify(request_id):
    confirm_msg = 'Do you confirm the reminders? Use 1 to confirm and any other digit to cancel.'
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addGetDigits(
        action=app.config['URL']+'/enable/'+job_id, 
        method="POST", 
        finishOnKey='#', 
        numDigits=1, 
        playBeep=True, 
        validDigits='1').addSpeak(body=confirm_msg)

    response.addSpeak(body="No Input recieved.")
    return Response(str(response), mimetype='text/xml')

#-------------------------------------------------------------------
@app.route('/enable/<job_id>', methods=['POST'])
def enable(request_id):
    if request.method == 'POST':
        data = request.form['Digits']
        print 'data veriy: ', data

        if data[0] == '1':
            print "Customer enabled"
            tasks.fire_bulk_call.delay(job_id)
        else:
            print "customer disabled"
        return "spawned calls"

#-------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.debug = True
    app.run(host='0.0.0.0', port=port)
