import json
import mmap
import flask
from datetime import datetime,date, timedelta
from flask import Flask,request,g,Response,url_for, render_template
from flask.ext.login import login_user, logout_user, current_user, login_required
from bson.objectid import ObjectId

# Move to reminders.py after refactor
from werkzeug import secure_filename
import codecs
import csv
import os
from dateutil.parser import parse

from app import flask_app, db, logger, login_manager, socketio
import reminders
import gsheets
import scheduler
import auth
from config import *
import utils

@flask_app.before_request
def before_request():
  g.user = current_user

@login_manager.user_loader
def load_user(username):
  return auth.load_user(username)

@flask_app.route('/login', methods=['GET','POST'])
def login():
  return auth.login()

@flask_app.route('/logout', methods=['GET'])
def logout():
  logout_user()
  logger.info('User logged out')
  return flask.redirect(PUB_URL)

@flask_app.route('/', methods=['GET'])
@login_required
def index():
  try:
    return reminders.view_main()
  except Exception as e:
    logger.info(str(e))
    return 'Fail'

@flask_app.route('/log')
@login_required
def view_log():
  n = 50
  size = os.path.getsize(LOG_FILE)

  with open(LOG_FILE, "rb") as f:
    fm = mmap.mmap(f.fileno(), 0, mmap.MAP_SHARED, mmap.PROT_READ)
    try:
      for i in xrange(size - 1, -1, -1):
        if fm[i] == '\n':
          n -= 1
          if n == -1:
            break
        lines = fm[i + 1 if i else 0:].splitlines()
    except Exception, e:
      logger.error('/log: %s', str(e))
    finally:
      fm.close()

  return flask.render_template('log.html', lines=lines)

@flask_app.route('/admin')
@login_required
def view_admin():
  return flask.render_template('admin.html')

@socketio.on('disconnected')
def socketio_disconnected():
  logger.debug('socket disconnected')
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )

@socketio.on('connected')
def socketio_connect():
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )
  socketio.emit('msg', 'ping from ' + DB_NAME + ' server!');

@flask_app.route('/sendsocket', methods=['GET'])
def request_send_socket():
  name = request.args.get('name').encode('utf-8')
  data = request.args.get('data').encode('utf-8')
  socketio.emit(name, data)
  return 'OK'

@flask_app.route('/reminders/new')
@login_required
def new_job():
  return render_template('new_job.html', title=TITLE)

@flask_app.route('/reminders/get_job_template/<name>')
def get_job_template(name):
  headers = []
  for col in TEMPLATE[name]:
    headers.append(col['header'])
  return json.dumps(headers)

@flask_app.route('/reminders/submit', methods=['POST'])
@login_required
def submit():
  try:
      # POST request to create new job from new_job.html template
      file = request.files['call_list']
      if file and reminders.allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename)) 
        file_path = UPLOAD_FOLDER + '/' + filename
      else:
        logger.info('could not save file')
        r = json.dumps({'status':'error', 'title': 'Filename Problem', 'msg':'Could not save file'})
        return Response(response=r, status=200, mimetype='application/json')
  except Exception as e:
      logger.info(str(e))
      return Response(response={'status':'error', 'title':'file problem', 'msg':'could not upload file'},status=200,mimetype='application/json')

  # Open and parse file
  try:
    with codecs.open(file_path, 'r', 'utf-8-sig') as f:
      logger.info('opened file')
      #if f[0] == unicode(codecs.BOM_UTF8, 'utf8'):
      #  logger.info('stripping BOM_UTF8 char')
      #  f.lstrip(unicode(codecs.BOM_UTF8, 'utf8'))
      buffer = reminders.parse_csv(f, TEMPLATE[request.form['template']])
      if type(buffer) == str:
        r = json.dumps({'status':'error', 'title': 'Problem Reading File', 'msg':buffer})
        return Response(response=r, status=200, mimetype='application/json')
      else:
        logger.info('Parsed %d rows from %s', len(buffer), filename) 
  except Exception as e:
    logger.error(str(e))
    r = json.dumps({'status':'error', 'title': 'Problem Reading File', 'msg':'Could not parse file: ' + str(e)})
    return Response(response=r, status=200, mimetype='application/json')

  try:
      if not request.form['job_name']:
        job_name = filename.split('.')[0].replace('_',' ')
      else:
        job_name = request.form['job_name']
      
      date_string = request.form['date']+' '+request.form['time']
      fire_dtime = parse(date_string)
      
      job = {
        'name': job_name,
        'template': request.form['template'],
        'fire_dtime': fire_dtime,
        'status': 'pending',
        'num_calls': len(buffer)
      }

      if request.form['template'] == 'announce_voice':
        job['audio_url'] = request.form['audio-url']
      elif request.form['template'] == 'announce_text':
        job['message'] = request.form['message']
        
      job_id = db['reminder_jobs'].insert(job)
      job['_id'] = job_id

      errors = []
      calls = []
      for idx, row in enumerate(buffer):
        call = reminders.call_db_doc(job, idx, row, errors)
        if call:
          calls.append(call)

      if len(errors) > 0:
        msg = 'The file <b>' + filename + '</b> has some errors:<br><br>'
        for error in errors:
          msg += error
        db['reminder_jobs'].remove({'_id':job_id})
        r = json.dumps({'status':'error', 'title':'File Format Problem', 'msg':msg})
        return Response(response=r, status=200, mimetype='application/json')

      db['reminder_msgs'].insert(calls)
      logger.info('Job "%s" Created [ID %s]', job_name, str(job_id))

      jobs = db['reminder_jobs'].find().sort('fire_dtime',-1)
      banner_msg = 'Job \'' + job_name + '\' successfully created! ' + str(len(calls)) + ' calls imported.'
      r = json.dumps({'status':'success', 'msg':banner_msg})

      if job['template'] == 'etw_reminder':
        scheduler.get_next_pickups.apply_async((str(job['_id']), ), queue=DB_NAME)
      
      return Response(response=r, status=200, mimetype='application/json')
  except Exception as e:
      logger.info(str(e))
      return Response(response={'status':'error', 'title':'error', 'msg':str(e)},status=500,mimetype='application/json')

@flask_app.route('/reminders/recordaudio', methods=['GET', 'POST'])
def record_msg():
  return reminders.record_audio()

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

@flask_app.route('/reminders/request/email/<job_id>')
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
        continue
        #send_socket('update_msg', {'id':str(message['_id']), 'email_status': 'no_email'})
      
      html = render_template('email_reminder.html', args={
        'name': message['imported']['name'],
        'recipient': message['imported']['email'],
        'next_pickup': message['imported']['event_date'],
        'status': message['imported']['status']
      })
      
      subject = 'Reminder: Upcoming event on  ' + message['imported']['event_date'].strftime('%A, %B %d')
      
      r = utils.send_email(message['imported']['email'], subject, html)
      r = json.loads(r.text)

      if r['message'].find('Queued') == 0:
        db['reminder_msgs'].update(
          {'_id':message['_id']}, 
          {'$set': {
            'mid':r['id'],
            'email_status': 'queued'
          }}
        )
          
        logger.info('%s %s', message['imported']['email'], 'queued')
        #send_socket('update_msg', {'id':str(message['_id']), 'email_status': 'queued'})
      else:
        logger.info('%s %s', message['imported']['email'], r['message'])
        #send_socket('update_msg', {'id':str(message['_id']), 'email_status': 'failed'})

    return 'OK'
  except Exception, e:
    logger.error('/request/email', exc_info=True)


@flask_app.route('/reminders/request/execute/<job_id>')
@login_required
def request_execute_job(job_id):
  job_id = job_id.encode('utf-8')
  # Start celery worker
  reminders.execute_job.apply_async((job_id, ), queue=DB_NAME)

  return 'OK'

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


@flask_app.route('/email/spam_complaint', methods=['POST'])
def email_spam_complaint():
  try:
      gsheets.create_rfu(request.form['recipient'] + ': received spam complaint')
      return 'OK'

  except Exception, e:
    logger.info('%s /email/spam_complaint' % request.values.items(), exc_info=True)
    return str(e)


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
      msg = db['reminder_msgs'].find_one({'_id':db_record['reminder_msg_id']})
      
      error_msg = ''
      if event == 'bounced':
        logger.info('%s %s (%s). %s', recipient, event, request.form['code'], request.form['error'])
        db['reminder_msgs'].update({email['mid']:mid},{'$set':{
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
  
      #socketio.emit('update_msg', {'id':str(msg['_id']), 'email_status': request.form['event']})
  
      return 'OK'
    
  except Exception, e:
    logger.info('%s /email/status' % request.values.items(), exc_info=True)
    return str(e)

@flask_app.route('/get_np', methods=['GET'])
def get_romorrow_accounts():
    scheduler.find_nps_in_schedule.apply_async(queue=DB_NAME)
    return 'Celery process started...'

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
