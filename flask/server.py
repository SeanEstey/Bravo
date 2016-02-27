import flask
from flask import Flask,render_template,request,g,Response,redirect,url_for
from flask.ext.login import LoginManager, login_user, logout_user, current_user, login_required
from flask.ext.socketio import *
from server_settings import *
from config import *
from bson import Binary, Code, json_util
from bson.objectid import ObjectId
import pymongo
import twilio
from twilio import twiml
from datetime import datetime,date
from dateutil.parser import parse
import werkzeug
from werkzeug import secure_filename
import os
import time
import csv
import logging
import codecs
import sys
import tasks
from user import User
import reminders
import utils
import requests
import mmap
import json
from oauth2client.client import SignedJwtAssertionCredentials
import gspread

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = PUB_URL + '/login' #url_for('login')

@app.route('/cal/<job_id>')
@login_required
def get_calendar_events(job_id):
  job_id = job_id.encode('utf-8')
  tasks.get_next_pickups.apply_async((job_id, ), queue=DB_NAME)
  return 'OK'


    
@app.route('/reminders/summarize/<job_id>')
@login_required
def get_job_summary(job_id):
  job_id = job_id.encode('utf-8')
  summary = json_util.dumps(job_db_dump(job_id))
  return render_template('job_summary.html', title=TITLE, summary=summary)

@app.route('/reminders/get/template/<name>')
def get_template(name):
  if not name in TEMPLATE:
    return False
  else:
    headers = []
    for col in TEMPLATE[name]:
      headers.append(col['header'])
    return json.dumps(headers)

@app.route('/reminders/get/<var>')
def get_var(var):
  if var == 'version':
    branch = os.popen('git rev-parse --abbrev-ref HEAD').read()
    revision = os.popen('git rev-list HEAD | wc -l').read()
    return branch + ' branch rev ' + revision + ' (' + DB_NAME + ' DB)'

  elif var == 'monthly_usage':
    client = twilio.rest.TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_ID)
    calls = client.usage.records.this_month.list(category='calls')[0]
    cost = client.usage.records.this_month.list(category='totalprice')[0]
    now = datetime.now()
    data = {
      'month': now.strftime('%B'),
      'calls': calls.count,
      'cost': '$' + cost.usage
    }
    return json.dumps(data)
  
  elif var == 'annual_usage':
    client = twilio.rest.TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_ID)
    calls = client.usage.records.yearly.list(category='calls')[0]
    cost = client.usage.records.yearly.list(category='totalprice')[0]
    now = datetime.now()
    data = {
      'year': now.strftime('%Y'),
      'calls': calls.count,
      'cost': '$' + cost.usage
    }
    return json.dumps(data)
  
  elif var == 'db_name':
    return 'DB: ' + DB_NAME
  
  elif var == 'pub_url':
    return PUB_URL
  
  elif var == 'celery_status':
    if not tasks.celery_app.control.inspect().active_queues():
      return 'Offline'
    else:
      return 'Online'
  
  elif var == 'sockets':
    if not socketio.server:
      return "No sockets"
    return 'Sockets: ' + str(len(socketio.server.sockets))
  
  return False

@app.route('/reminders/error')
def show_error():
  msg = request.args['msg']
  return render_template('error.html', title=TITLE, msg=msg)



# Requested from client
@app.route('/reminders/request/execute/<job_id>')
@login_required
def request_execute_job(job_id):
  job_id = job_id.encode('utf-8')
  tasks.execute_job.apply_async((job_id, ), queue=DB_NAME)

  return 'OK'

@app.route('/reminders/request/email/<job_id>')
@login_required
def request_email_job(job_id):
  try:
    job_id = job_id.encode('utf-8')
    job = db['reminder_jobs'].find_one({'_id':ObjectId(job_id)})
    messages = db['reminder_msgs'].find({'job_id':ObjectId(job_id)})
    emails = []
    for message in messages:
      if message['email_status'] != 'pending':
        continue
      if not message['imported']['email']:
        db['reminder_msgs'].update(
          {'_id':message['_id']}, 
          {'$set': {'email_status': 'no_email'}}
        )
        send_socket('update_msg', {'id':str(message['_id']), 'email_status': 'no_email'})
      else:
        body = reminders.get_reminder_html_body(job, message)
        if not body:
          continue
        subject = 'Pickup on ' + message['imported']['event_date'].strftime('%A, %B %d')
        r = utils.send_email([message['imported']['email']], subject, body)
        
        r = json.loads(r.text)

        if r['message'].find('Queued') == 0:
          db['reminder_msgs'].update(
            {'_id':message['_id']}, 
            {'$set': {
              'mid':r['id'],
              'email_status': 'queued'
              }
            }
          )
          logger.info('%s %s', message['imported']['email'], 'queued')
          send_socket('update_msg', {'id':str(message['_id']), 'email_status': 'queued'})
        else:
          logger.info('%s %s', message['imported']['email'], r['message'])
          send_socket('update_msg', {'id':str(message['_id']), 'email_status': 'failed'})

    return 'OK'
  except Exception, e:
    logger.error('/request/email', exc_info=True)


  
@app.route('/request/send_reminder', methods=['POST'])
def send_reminder_email():
  if request.method == 'POST':
    html = render_template(
      'email_reminder.html',
      next_pickup = request.form['next_pickup']
    )

    utils.send_email([request.form['to']], 'Your upcoming Empties to Winn pickup', html)

    return 'OK'

@app.route('/reminders/jobs/<job_id>')
@login_required
def show_calls(job_id):
  sort_by = 'name' 
  calls = db['reminder_msgs'].find({'job_id':ObjectId(job_id)}).sort(sort_by, 1)
  job = db['reminder_jobs'].find_one({'_id':ObjectId(job_id)})

  return render_template(
    'show_calls.html', 
    title=TITLE,
    calls=calls, 
    job_id=job_id, 
    job=job,
    template=TEMPLATE[job['template']]
  )


# Requested on completion of tasks.execute_job()
@app.route('/reminders/fired/<job_id>')
def job_fired(job_id):
  tasks.monitor_job.apply_async((job_id.encode('utf-8'), ), queue=DB_NAME)
  return 'OK'
  

@app.route('/reminders/complete/<job_id>')
#@login_required
# Prevent this request from coming externally. Comes via Celery task now
# but can be spoofed easily
def job_complete(job_id):
  data = {
    'id': job_id,
    'status': 'completed'
  }
  job_id = job_id.encode('utf-8')
  
  send_socket('update_job', data)
  reminders.send_email_report(job_id)

  return 'OK'

@app.route('/reminders/reset/<job_id>')
@login_required
def reset_job(job_id):
  db['reminder_msgs'].update(
    {'job_id': ObjectId(job_id)}, 
    {'$set': {
      # TODO: only include status fields defined by Template
      'call_status': 'pending',
      'email_status': 'pending',
      'attempts': 0
    }},
    multi=True
  )

  db['reminder_msgs'].update(
    {'job_id': ObjectId(job_id)}, 
    {'$unset': {
      'answered_by': '',
      'call_duration': '',
      'mid': '',
      'call_error': '',
      'error_code': '',
      'message': '',
      'sid': '',
      'speak': '',
      'code': '',
      'ended_at': '',
      'rfu': '',
      'no_pickup': '',
      'next_pickup': ''
    }},
    multi=True
  )

  db['reminder_jobs'].update(
    {'_id':ObjectId(job_id)},
    {'$set': {
      'status': 'pending'
    }})


  job = db['reminder_jobs'].find_one({'_id':ObjectId(job_id)})
  if job['template'] == 'etw_reminder':
    tasks.get_next_pickups.apply_async((str(job['_id']), ), queue=DB_NAME)

  logger.info('Reset Job [ID %s]', str(job_id))
  return 'OK'

@app.route('/reminders/cancel/job/<job_id>')
@login_required
def cancel_job(job_id):
  db['reminder_jobs'].remove({'_id':ObjectId(job_id)})
  db['reminder_msgs'].remove({'job_id':ObjectId(job_id)})
  logger.info('Removed Job [ID %s]', str(job_id))

  return 'OK'

@app.route('/reminders/cancel/call', methods=['POST'])
@login_required
def cancel_call():
  call_uuid = request.form.get('call_uuid')
  job_uuid = request.form.get('job_uuid')
  db['reminder_msgs'].remove({'_id':ObjectId(call_uuid)})
   
  db['reminder_jobs'].update(
    {'_id':ObjectId(job_uuid)}, 
    {'$inc':{'num_calls':-1}}
  )

  return 'OK'

@app.route('/reminders/nopickup/<msg_id>', methods=['GET'])
# Script run via reminder email
def no_pickup(msg_id):
  try:
    msg = db['reminder_msgs'].find_one({'_id':ObjectId(msg_id)})
    # Link clicked for an outdated/in-progress or deleted job?
    if not msg:
      logger.info('No pickup request fail. Invalid msg_id')
      return 'Request unsuccessful'

    if 'no_pickup' in msg:
      logger.info('No pickup already processed for account %s', msg['imported']['account'])
      return 'Thank you'

    job = db['reminder_jobs'].find_one({'_id':msg['job_id']})

    no_pickup = 'No Pickup ' + msg['imported']['event_date'].strftime('%A, %B %d')
    db['reminder_msgs'].update(
      {'_id':msg['_id']},
      {'$set': {
        'imported.office_notes': no_pickup,
        'no_pickup': True
      }}
    )
    send_socket('update_msg', {
      'id': str(msg['_id']),
      'office_notes':no_pickup
      })

    # Write to eTapestry
    if 'account' in msg['imported']:
      url = 'http://bravovoice.ca/etap/etap.php'
      params = {
        'func':'no_pickup', 
        'account': msg['imported']['account'], 
        'date': msg['imported']['event_date'].strftime('%d/%m/%Y'),
        'next_pickup': msg['next_pickup'].strftime('%d/%m/%Y')
      }
      tasks.no_pickup_etapestry.apply_async((url, params, ), queue=DB_NAME)

    # Send email w/ next pickup
    if 'next_pickup' in msg:
      subject = 'Your next Pickup'
      body = reminders.get_no_pickup_html_body(msg['next_pickup'])
      utils.send_email([msg['imported']['email']], subject, body)
      logger.info('Emailed Next Pickup to %s', msg['imported']['email'])
    
    return 'Thank you'
  
  except Exception, e:
    logger.error('/nopickup/msg_id', exc_info=True)
    return str(e)
   

@app.route('/reminders/edit/call/<sid>', methods=['POST'])
@login_required
def edit_call(sid):
  for fieldname, value in request.form.items():
    if fieldname == 'event_date':
      try:
        value = parse(value)
      except Exception, e:
        logger.error('Could not parse event_date in /edit/call')
        return '400'
    logger.info('Editing ' + fieldname + ' to value: ' + str(value))
    field = 'imported.'+fieldname
    db['reminder_msgs'].update(
        {'_id':ObjectId(sid)}, 
        {'$set':{field: value}}
    )
  return 'OK'


@app.route('/reminders/call/answer',methods=['POST','GET'])
def content():
  try:
    if request.method == 'POST':
      sid = request.form.get('CallSid')
      call_status = request.form.get('CallStatus')
      to = request.form.get('To')
      answered_by = ''
      if 'AnsweredBy' in request.form:
        answered_by = request.form.get('AnsweredBy')
      logger.info('%s %s (%s)', to, call_status, answered_by)
      call = db['reminder_msgs'].find_one({'sid':sid})

      if not call:
        # Might be special msg voice record call
        record = db['bravo'].find_one({'sid':sid})
        if record:
          logger.info('Sending record twimlo response to client')
          # Record voice message
          response = twilio.twiml.Response()
          response.say('Record your message after the beep. Press pound when complete.', voice='alice')
          response.record(
            method= 'GET',
            action= PUB_URL+'/recordaudio',
            playBeep= True,
            finishOnKey='#'
          )
          send_socket('record_audio', {'msg': 'Listen to the call for instructions'}) 
          return Response(str(response), mimetype='text/xml')

      else:
        db['reminder_msgs'].update(
          {'sid':sid},
          {'$set': {'call_status':call_status}}
        )
        call = db['reminder_msgs'].find_one({'sid':sid})
        send_socket(
          'update_msg', {
            'id': str(call['_id']),
            'call_status': call_status
          }
        )
        job = db['reminder_jobs'].find_one({'_id':call['job_id']})
        
        return reminders.get_speak(job, call, answered_by)
     
    elif request.method == "GET":
      sid = request.args.get('CallSid')
      call = db['reminder_msgs'].find_one({'sid':sid})
      job = db['reminder_jobs'].find_one({'_id':call['job_id']})
      digits = request.args.get('Digits')
      # Repeat Msg
      if digits == '1':
        return reminders.get_speak(job, call, 'human')
      # Special Action (defined by template)
      elif digits == '2' and 'no_pickup' not in call:
        no_pickup = 'No Pickup ' + call['imported']['event_date'].strftime('%A, %B %d')
        db['reminder_msgs'].update(
          {'sid':sid},
          {'$set': {'imported.office_notes': no_pickup}}
        )
        send_socket('update_msg', {
          'id': str(call['_id']),
          'office_notes':no_pickup
          })
        # Write to eTapestry
        if 'account' in call['imported']:
          url = 'http://bravovoice.ca/etap/etap.php'
          params = {
            'func': 'no_pickup', 
            'account': call['imported']['account'], 
            'date':  call['imported']['event_date'].strftime('%d/%m/%Y'),
            'next_pickup': call['next_pickup'].strftime('%d/%m/%Y')
          }
          tasks.no_pickup_etapestry.apply_async((url, params, ), queue=DB_NAME)

        if call['next_pickup']:
          response = twilio.twiml.Response()
          next_pickup_str = call['next_pickup'].strftime('%A, %B %d')
          response.say('Thank you. Your next pickup will be on ' + next_pickup_str + '. Goodbye', voice='alice')
          return Response(str(response), mimetype='text/xml')

    response = twilio.twiml.Response()
    response.say('Goodbye', voice='alice')
    
    return Response(str(response), mimetype='text/xml')
  except Exception, e:
    logger.error('/call/answer', exc_info=True)
    
    return str(e)


@app.route('/reminders/call/status',methods=['POST','GET'])
def process_status():
  try:
    logger.debug('/call/status values: %s' % request.values.items())
    sid = request.form.get('CallSid')
    to = request.form.get('To')
    call_status = request.form.get('CallStatus')
    logger.info('%s %s', to, call_status)
    fields = {
      'call_status': call_status,
      'ended_at': datetime.now(),
      'call_duration': request.form.get('CallDuration')
    }
    call = db['reminder_msgs'].find_one({'sid':sid})

    if not call:
      # Might be an audio recording call
      call = db['bravo'].find_one({'sid':sid})
      if call:
        logger.info('Record audio call complete')
        db['bravo'].update({'sid':sid}, {'$set': {'call_status':call_status}})
      return 'OK'

    if call_status == 'completed':
      answered_by = request.form.get('AnsweredBy')
      fields['answered_by'] = answered_by
      if 'speak' in call:
        fields['speak'] = call['speak']
    elif call_status == 'failed':
      fields['call_error'] = 'unknown_error'
      logger.info('/call/status dump: %s', request.values.items())

    db['reminder_msgs'].update(
      {'sid':sid},
      {'$set': fields}
    )
    fields['id'] = str(call['_id'])
    fields['attempts'] = call['attempts']
    send_socket('update_msg', fields)
    return 'OK'
  except Exception, e:
    logger.error('%s /call/status' % request.values.items(), exc_info=True)
    return str(e)


@app.route('/reminders/sms/status', methods=['POST'])
def sms_status():
  try:
    # Using 'call_status' in DB TEMPORARILY!!!!
    items = str(request.form.items())
    logger.info(items)
    sid = request.form.get('SmsSid')
    sms_status = request.form.get('SmsStatus')
    msg_doc = db['reminder_msgs'].find_one({'sid':sid})
    if not msg_doc:
      logger.info('SmsSid not found in DB')
      return 'FAIL'

    # TODO: replace 'call_status' with 'sms_status' and refactor code
    db['reminder_msgs'].update(
      {'sid':sid},
      {'$set': {'call_status': sms_status}}
    )
    fields = {
      'id': str(msg_doc['_id']),
      'call_status': sms_status
    }
    send_socket('update_msg', fields)

    return 'OK'
  except Exception, e:
    return str(e)


@app.route('/reminders/call/fallback',methods=['POST','GET'])
def process_fallback():
  try:
    '''
    post_data = str(request.form.values())
    print post_data
    logger.info('call fallback data: %s' % post_data)
    return Response(str(response), mimetype='text/xml')
    '''
    return 'OK'
  except Exception, e:
    logger.error('%s /call/fallback' % request.values.items(), exc_info=True)
    return str(e)


@app.route('/email/opened', methods=['POST'])
def email_opened():
  try:
    event = request.form['event']
    recipient = request.form['recipient']
   
    #logger.info('Email opened by ' + recipient)
    
    mid = '<' + request.form['message-id'] + '>'
    
    db['email_status'].update(
      {'mid': mid},
      {'$set': {'opened': True}}
    )

    return 'OK'
  except Exception, e:
    logger.error('%s /email/opened' % request.values.items(), exc_info=True)
    return str(e)

@app.route('/email/status',methods=['POST'])
def email_status():
  # Relay for all Mailgun webhooks (delivered, bounced, dropped, etc)
  # Can be from Reminders app, Signups sheet, or Route Importer sheet 
  try:
    # Forwarded from bravovoice.ca. Change webhooks in Mailgun once
    # reminders switched to this VPS 
    event = request.form['event']
    recipient = request.form['recipient']
    mid = request.form['mid']

    db_record = db['email_status'].find_one({'mid':mid})

    if not db_record:
      logger.info('Reminder email to ' + recipient + ' ' + event)
      return 'OK'
    else:
      logger.info('Email to ' + recipient + ' ' + event)
    
    db['email_status'].update(
      {'mid': mid},
      {'$set': {'status': event}}
    )

    # Did email originate from Google Sheet?
    if 'sheet_name' in db_record:
      json_key = json.load(open('oauth_credentials.json'))
      scope = ['https://spreadsheets.google.com/feeds', 'https://docs.google.com/feeds']
      credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)
      gc = gspread.authorize(credentials)
      
      sheet = gc.open(db_record['sheet_name'])
      wks = sheet.worksheet(db_record['worksheet_name'])

      headers = wks.row_values(1)
      
      # Make sure the row entry still exists in the worksheet
      cell = wks.cell(db_record['row'], headers.index('Upload Status')+1)

      if cell:
        if str(cell.value) == db_record['upload_status']:
          wks.update_cell(db_record['row'], headers.index('Email Status')+1, event)

      # Create RFU if event is dropped/bounced and is from a collection receipt
      if db_record['worksheet_name'] == 'Routes':
          if event == 'dropped' or event == 'bounced':
            wks = sheet.worksheet('RFU')
            headers = wks.row_values(1)
            
            rfu = [''] * len(headers)
            rfu[headers.index('Request Note')] = 'Email ' + db_record['recipient'] + ' dropped.'

            if 'account_number' in db_record:
              rfu[headers.index('Account Number')] = db_record['account_number']

            logger.info('Creating RFU for bounced/dropped email: ' + json.dumps(rfu))
            wks.append_row(rfu)

    return 'OK'

    '''
    mid = request.form['Message-Id']
    msg = db['reminder_msgs'].find_one({'mid':mid})
    # Email may be for job summary or other purposes not needing this webhook callback
    if not msg:
      return 'No mid matching email' 
    
    error_msg = ''
    if event == 'bounced':
      logger.info('%s %s (%s). %s', recipient, event, request.form['code'], request.form['error'])
      db['reminder_msgs'].update({'mid':mid},{'$set':{
        'email_status': event,
        'email_error': request.form['code'] + '. ' + request.form['error']
        }}
      )
    elif event == 'dropped':
      # Don't overwrite a bounced with a dropped status
      if msg['email_status'] == 'bounced':
        event = 'bounced'
      
      logger.info('%s %s (%s). %s', recipient, event, request.form['reason'], request.form['description'])
      db['reminder_msgs'].update({'mid':mid},{'$set':{
        'email_status': event,
        'email_error': request.form['reason'] + '. ' + request.form['description']
        }}
      )
    else:
      logger.info('%s %s', recipient, event)
      db['reminder_msgs'].update({'mid':mid},{'$set':{'email_status':event}})

    send_socket('update_msg', {'id':str(msg['_id']), 'email_status': request.form['event']})

    return 'OK'
    '''
  except Exception, e:
    logger.info('%s /email/status' % request.values.items(), exc_info=True)
    return str(e)

