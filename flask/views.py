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
def view_jobs():
  return render_template(
    'view_jobs.html', 
    title=None,
    jobs=reminders.get_jobs(request.args.values())
  )

#-------------------------------------------------------------------------------
@flask_app.route('/log')
@login_required
def view_log():
  lines = log.get_tail(LOG_FILE, 50):
  return flask.render_template('view_log.html', lines=lines)

#-------------------------------------------------------------------------------
@flask_app.route('/admin')
@login_required
def view_admin():
  return flask.render_template('view_admin.html')

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
  return render_template('view_new_job.html', title=TITLE)

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/get_job_template/<name>')
def get_job_template(name):
  headers = []
  for col in TEMPLATE[name]:
    headers.append(col['header'])
  return json.dumps(headers)

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/submit_job', methods=['POST'])
@login_required
def submit_job():
  r = reminders.submit_job(request.form.values(), request.files['call_list'])
  return Response(response=json.dumps(r), status=200, mimetype='application/json')

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/recordaudio', methods=['GET', 'POST'])
def record_msg():
  return reminders.record_audio()

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>')
@login_required
def view_job(job_id):
  sort_by = 'name' 
  calls = db['reminder_msgs'].find({'job_id':ObjectId(job_id)}).sort(sort_by, 1)
  job = db['reminder_jobs'].find_one({'_id':ObjectId(job_id)})

  return render_template(
    'view_job.html', 
    title=TITLE,
    calls=calls, 
    job_id=job_id, 
    job=job,
    template=job['template']['import_fields']
  )

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/cancel')
@login_required
def cancel_job(job_id):
  return reminders.cancel_job(job_id)

#-------------------------------------------------------------------------------
# Requested on completion of tasks.execute_job()
@flask_app.route('/reminders/<job_id>/monitor')
def monitor_job(job_id):
  reminders.monitor_calls.apply_async((job_id.encode('utf-8'),), queue=DB_NAME)
  return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/send_emails')
@login_required
def send_emails(job_id):
  reminders.send_emails.apply_async((job_id.encode('utf-8'),), queue=DB_NAME)
  return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/send_calls')
@login_required
def send_calls(job_id):
  job_id = job_id.encode('utf-8')
  # Start celery worker
  reminders.send_calls.apply_async((job_id, ), queue=DB_NAME)
  return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/<msg_id>/remove', methods=['POST'])
@login_required
def rmv_msg():
  reminders.rmv_msg(job_id, msg_id)
  return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/<msg_id>/edit', methods=['POST'])
@login_required
def edit_msg(sid):
  reminders.edit_msg(job_id, msg_id, form.items()) 
  return 'OK'
  
#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/<msg_id>/cancel_pickup', methods=['GET'])
# Script run via reminder email
def no_pickup(msg_id):
  reminders.cancel_pickup.apply_async((msg_id,), queue=DB_NAME)
  return 'Thank You'
  
#-------------------------------------------------------------------------------
# Twilio callback
@flask_app.route('/reminders/call_action',methods=['POST','GET'])
def call_action():
  if request.form.get('msg') or request.form.get('Digits'):
    response = reminders.call_interaction(request.values.to_dict())
  else:
    response = reminders.call_answered(request.values.to_dict())
    
  return Response(str(response), mimetype='text/xml')
  
#-------------------------------------------------------------------------------
# Twilio callback
@flask_app.route('/reminders/call_ended',methods=['POST','GET'])
def call_ended():
  reminders.call_ended(request.form.to_dict())
  return 'OK'

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
# Relay for all Mailgun webhooks: delivered, bounced, dropped, etc
# Email can originate from reminder_msg, Signups sheet, or Route Importer sheet 
@flask_app.route('/email/status',methods=['POST'])
def email_status():

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
  
  try:
    
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
