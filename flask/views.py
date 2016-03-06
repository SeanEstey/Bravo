import json
import flask
from datetime import datetime,date, timedelta
from flask import Flask,request,g,Response,url_for, render_template
from flask.ext.login import login_user, logout_user, current_user, login_required
from bson.objectid import ObjectId

from app import flask_app, db, logger, login_manager, socketio
import reminders
import log
import gsheets
import scheduler
import auth
from config import *
import utils

#-------------------------------------------------------------------------------
@flask_app.before_request
def before_request():
  g.user = current_user

#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(username):
  return auth.load_user(username)

#-------------------------------------------------------------------------------
@flask_app.route('/login', methods=['GET','POST'])
def login():
  return auth.login()

#-------------------------------------------------------------------------------
@flask_app.route('/logout', methods=['GET'])
def logout():
  logout_user()
  logger.info('User logged out')
  return flask.redirect(PUB_URL)

#-------------------------------------------------------------------------------
@flask_app.route('/', methods=['GET'])
@login_required
def index():
  try:
    return reminders.view_main()
  except Exception as e:
    logger.info(str(e))
    return 'Fail'

#-------------------------------------------------------------------------------
@flask_app.route('/log')
@login_required
def view_log():
  lines = log.get_tail(LOG_FILE, 50):
  return flask.render_template('log.html', lines=lines)

#-------------------------------------------------------------------------------
@flask_app.route('/admin')
@login_required
def view_admin():
  return flask.render_template('admin.html')

#-------------------------------------------------------------------------------
@socketio.on('disconnected')
def socketio_disconnected():
  logger.debug('socket disconnected')
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )

#-------------------------------------------------------------------------------
@socketio.on('connected')
def socketio_connect():
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )
  socketio.emit('msg', 'ping from ' + DB_NAME + ' server!');

#-------------------------------------------------------------------------------
@flask_app.route('/sendsocket', methods=['GET'])
def request_send_socket():
  name = request.args.get('name').encode('utf-8')
  data = request.args.get('data').encode('utf-8')
  socketio.emit(name, data)
  return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/new')
@login_required
def new_job():
  return render_template('new_job.html', title=TITLE)

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/get_job_template/<name>')
def get_job_template(name):
  headers = []
  for col in TEMPLATE[name]:
    headers.append(col['header'])
  return json.dumps(headers)

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/submit', methods=['POST'])
@login_required
def submit():
  file = request.files['call_list']
  r = reminders.submit_job(request.form, file)
  return Response(response=json.dumps(r), status=200, mimetype='application/json')

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/recordaudio', methods=['GET', 'POST'])
def record_msg():
  return reminders.record_audio()

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/jobs/<job_id>')
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

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/cancel/job/<job_id>')
@login_required
def cancel_job(job_id):
  try:
      db['reminder_jobs'].remove({'_id':ObjectId(job_id)})
      db['reminder_msgs'].remove({'job_id':ObjectId(job_id)})
      logger.info('Removed Job [ID %s]', str(job_id))

      return 'OK'
  except Exception as e:
      logger.info(str(e))
      return 'error'

#-------------------------------------------------------------------------------
# Requested on completion of tasks.execute_job()
@flask_app.route('/reminders/<job_id>/monitor')
def monitor_job(job_id):
  reminders.monitor_calls.apply_async((job_id.encode('utf-8'), ), queue=DB_NAME)
  return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/send_emails')
@login_required
def send_reminder_emails(job_id):
  reminders.send_emails(job_id)
  return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/send_calls')
@login_required
def send_reminder_calls(job_id):
  job_id = job_id.encode('utf-8')
  # Start celery worker
  reminders.send_calls.apply_async((job_id, ), queue=DB_NAME)
  return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/cancel/call', methods=['POST'])
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

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/cancel_pickup/<msg_id>', methods=['GET'])
# Script run via reminder email
def no_pickup(msg_id):
  reminders.cancel_pickup.apply_async((msg_id,), queue=DB_NAME)
  return 'Thank You'
   
#-------------------------------------------------------------------------------
@flask_app.route('/reminders/edit/call/<sid>', methods=['POST'])
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
  
#-------------------------------------------------------------------------------
@flask_app.route('/reminders/call/answer',methods=['POST','GET'])
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
  
#-------------------------------------------------------------------------------
@flask_app.route('/reminders/call/status',methods=['POST','GET'])
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


#-------------------------------------------------------------------------------
# Data sent from Routes worksheet in Gift Importer (Google Sheet)
@flask_app.route('/collections/process_receipts', methods=['POST'])
def process_receipts():
  try:
    # If sent via JSON by CURL from unit tests...
    if request.get_json():
      args = request.get_json()
      entries = args['data']
      keys = args['keys']
    else:
        entries = json.loads(request.form['data'])
        keys = json.loads(request.form['keys'])

    # Start celery workers to run slow eTapestry API calls
    gsheets.process_receipts.apply_async((entries, keys, ), queue=DB_NAME)

    return 'OK'

  except Exception, e:
    logger.error('/collections/process_receipts', exc_info=True)

#-------------------------------------------------------------------------------
# Can be collection receipt from gsheets.process_receipts, reminder email, or welcome letter from Google Sheets.
# Required fields: 'recipient', 'template', 'subject'
# Required fields for updating Google Sheets: 'sheet_name', 'worksheet_name', 'row', 'upload_status'
@flask_app.route('/email/send', methods=['POST'])
def send_email(): 
  try:
    args = request.get_json(force=True)

    html = render_template(args['template'], args=args)

    r = utils.send_email(args['recipient'], args['subject'], html)
    r = json.loads(r.text)
    
    if r['message'].find('Queued') == 0:
      db['email_status'].insert({
        "mid": r['id'],
        "status": "queued",
        "data": args
      })

      logger.info('Queued email to ' + args['recipient'])

    return 'OK'

  except Exception, e:
    logger.error('/email/send', exc_info=True)

#-------------------------------------------------------------------------------
@flask_app.route('/email/opened', methods=['POST'])
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

#-------------------------------------------------------------------------------
@flask_app.route('/email/unsubscribe', methods=['GET'])
def email_unsubscribe():
  try:
      if request.args.get('email'):
          msg = 'Contributor ' + request.args['email'] + ' has requested to unsubscribe \
                from Empties to Winn emails. Please contact to see if they want to cancel \
                the entire service.'
          
          utils.send_email(
            ['emptiestowinn@wsaf.ca'], 
            'Unsubscribe request', 
            msg
          )

          return 'We have received your request to unsubscribe ' + request.args['email'] + ' \
                  from Empties to Winn. If you wish to cancel the service, please allow us \
                  to contact you once more to arrange for retrieval of the Bag Buddy or other \
                  collection materials provided to you. As a non-profit, this allows us to \
                  spread out our costs.'

  except Exception, e:
    logger.info('%s /email/unsubscribe' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
@flask_app.route('/email/spam_complaint', methods=['POST'])
def email_spam_complaint():
  try:
      gsheets.create_rfu(request.form['recipient'] + ': received spam complaint')
      return 'OK'

  except Exception, e:
    logger.info('%s /email/spam_complaint' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
@flask_app.route('/email/status',methods=['POST'])
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
      
    logger.info('Email to ' + recipient + ' ' + event)
    
    db['email_status'].update(
      {'mid': mid},
      {'$set': {'status': event}}
    )
    
    db_record['status'] = event
    
    if not 'data' in db_record:
      return 'OK'
    
    # Where did this email originate from?
    
    # Google Sheets?
    if 'sheet_name' in db_record['data']:
      gsheets.update_entry(db_record['data'])
      return 'OK'
    
    # A reminder email?
    if 'reminder_msg_id' in db_record['data']:
      msg = db['reminder_msgs'].find_one({'_id':db_record['data']['reminder_msg_id']})
      
      if event == 'bounced':
        logger.info('%s %s (%s). %s', recipient, event, request.form['code'], request.form['error'])
        
        db['reminder_msgs'].update({email['mid']: mid}, {'$set':{
          "email.status": event,
          "email.error": request.form['code'] + '. ' + request.form['error']
        }})
      elif event == 'dropped':
        logger.info('%s %s (%s). %s', recipient, event, request.form['reason'], request.form['description'])
        
        db['reminder_msgs'].update({email['mid']: mid},{'$set':{
          "email.status": event,
          "email.error": request.form['reason'] + '. ' + request.form['description']
        }})
      else:
        logger.info('%s %s', recipient, event)
        db['reminder_msgs'].update({email['mid']: mid},{'$set':{"email.status": event}})
  
      #socketio.emit('update_msg', {'id':str(msg['_id']), 'email_status': request.form['event']})
  
      return 'OK'
    
  except Exception, e:
    logger.info('%s /email/status' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
@flask_app.route('/get_np', methods=['GET'])
def get_romorrow_accounts():
    scheduler.find_nps_in_schedule.apply_async(queue=DB_NAME)
    return 'Celery process started...'

#-------------------------------------------------------------------------------
@flask_app.route('/call/nis', methods=['POST'])
def nis():
    try:
        ''' 
        MongoDB record passed in with format: { 
        "_id" : ObjectId("56ba35a2693785608683f3e6"), 
        "next_pickup" : ISODate("2016-04-21T00:00:00Z"), 
        "imported" : { 
            "status" : "Dropoff", 
            "account" : "71535", 
            "name" : "Harish Kumar", 
            "office_notes" : "", 
            "to" : "7804652323", 
            "event_date" : ISODate("2016-02-11T00:00:00Z"), 
            "email" : "", 
            "block" : "R10J" 
        }, 
        "job_id" : ObjectId("56ba35a2693785608683f31c"), 
        "call_status" : "pending", 
        "attempts" : 0, 
        "email_status" : "no_email" 
        }
        '''

        logger.info('NIS!')

        record = request.get_json()

        gsheets.create_rfu(
            record['imported']['to'] + ' not in service', 
            account_number=record['imported']['account'], 
            block=record['imported']['block']
        )
        
        return False

    except Exception, e:
        logger.info('%s /call/nis' % request.values.items(), exc_info=True)
        return str(e)

#-------------------------------------------------------------------------------
# Forwarded signup submision from emptiestowinn.com
# Adds signup data to Route Importer->Signups gsheet row
@flask_app.route('/receive_signup', methods=['POST'])
def rec_signup():
  try:
      signup = request.form.to_dict()
      logger.info('New signup received: ' + signup['first_name'] + ' ' + signup['last_name'])
      gsheets.add_signup_row.apply_async((request.form.to_dict(), ), queue=DB_NAME)
      return 'OK'
  except Exception, e:
    logger.info('%s /receive_signup' % request.values.items(), exc_info=True)
    return str(e)
