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

client = pymongo.MongoClient('localhost',27017)
db = client['wsf']
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

    print "Request %s processed for %s." % (job_id, fire_dtime)
    return job_id

#-------------------------------------------------------------------
@app.route('/')
def index():
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

        print "Pushing request!", request.form

        job_id = push_data(
            request.form['verify_phone'],
            request.form['message'],
            request.form['audio'],
            order, 
            request.form['csv'],
            fire_dtime
        )

        print "We have a lift of"
        return "Got Data: Messge id is %s" % job_id

#-------------------------------------------------------------------
@app.route('/call/answer',methods=['POST','GET'])
def content():
  try:
    print "Call answered %s" % request.values.items()

    request_uuid = request.form.get('RequestUUID')
    call_uuid = request.form.get('CallUUID')
    
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'_id':request_uuid}, 
        {'$set':{
            'status': 'answered',
            'message': 'delivered', 
            'call_uuid': call_uuid
            }}
    )
    call = db['calls'].find_one({'_id':request_uuid})
    dt = parse(call['event_date'])
    date_str = dt.strftime('%A, %B %d')
    speak = 'Hi, this is a friendly reminder from the Winny Fred stewart association that your next empties to winn pickup date is ' + date_str + '. please have your empties out by 8am. to repeat this message press 1.'
   
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addSpeak(body=speak)
    return Response(str(response), mimetype='text/xml')
  
  except Exception, e:
    print str(e)
    return "ERROR %s" % str(e)

#-------------------------------------------------------------------
@app.route('/call/hangup',methods=['POST','GET'])
def process_hangup():
  try:
    print "Call hungup %s" % request.values.items()

    request_uuid = request.form.get('RequestUUID')
    
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'_id':request_uuid}, 
        {'$set': {'status':'hungup'}}
    )

    response = plivoxml.Response()
    return Response(str(response), mimetype='text/xml')
  
  except Exception, e:
    print str(e)
    return "ERROR %s" % str(e)

#-------------------------------------------------------------------
@app.route('/call/machine',methods=['POST','GET'])
def process_machine():
  try:
    
    # This is an asynchronous notice. Re-route the call to
    # leave a voicemail.

    print "Machine detected %s" % request.values.items()

    to = request.form.get('To', None)
    request_uuid = request.form.get('RequestUUID')
    call_uuid = request.form.get('CallUUID')

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'_id':request_uuid}, 
        {'$set': {'status':'machine'}}
    )
    
    server = plivo.RestAPI(AUTH_ID, AUTH_TOKEN)
    params = {
        'call_uuid': call_uuid,
        'legs': 'aleg',
        'aleg_url' : URL+'/call/voicemail',
        'aleg_method': 'POST',
    }
    print 'params for transfer: ' + str(params)
    resp  = server.transfer_call(params)
    print 'result of transfer: ' + str(resp)

    # response = plivoxml.Response()
    return Response(str(resp), mimetype='text/xml')
  
  except Exception, e:
    print str(e)
    return "ERROR %s" % str(e)

#-------------------------------------------------------------------
@app.route('/call/voicemail',methods=['POST','GET'])
def process_voicemail():
  try:
    print "Leaving voicemail %s" % request.values.items()

    request_uuid = request.form.get('RequestUUID')
    
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'_id':request_uuid}, 
        {'$set': {
            'status':'voicemail',
            'message': 'left voicemail'
            }}
    )
    call = db['calls'].find_one({'_id':request_uuid})
    dt = parse(call['event_date'])
    date_str = dt.strftime('%A, %B %d')
    speak = 'Hi, this is a friendly reminder from the winny fred stewart association that your next empties to winn pickup date is ' + date_str
   
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addSpeak(body=speak)
    return Response(str(response), mimetype='text/xml')
  
  except Exception, e:
    print str(e)
    return "ERROR %s" % str(e)

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
