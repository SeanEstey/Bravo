import json
import flask
from flask import Flask,request,g,Response,url_for
from flask.ext.login import login_user, logout_user, current_user, login_required

import app
from app import app, db, logger, login_manager
import reminders
import auth
from config import *

@app.before_request
def before_request():
  g.user = current_user

@login_manager.user_loader
def load_user(username):
  return auth.load_user(username)

@app.route('/login', methods=['GET','POST'])
def login():
  return auth.login()

@app.route('/logout', methods=['GET'])
def logout():
  logout_user()
  logger.info('User logged out')
  return flask.redirect(PUB_URL)

@app.route('/', methods=['GET'])
@login_required
def index():
  return reminders.view_main()

@app.route('/log')
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

@app.route('/admin')
@login_required
def view_admin():
  return flask.render_template('admin.html')

@app.route('/reminders/new')
@login_required
def new_job():
  return flask.render_template('new_job.html', title=TITLE)

@app.route('/reminders/recordaudio', methods=['GET', 'POST'])
def record_msg():
  return reminders.record_audio()

@app.route('/reminders/request/execute/<job_id>')
@login_required
def request_execute_job(job_id):
  job_id = job_id.encode('utf-8')
  # Start celery worker
  reminders.execute_job.apply_async((job_id, ), queue=DB_NAME)

  return 'OK'

@app.route('/collections/send_receipts', methods=['POST'])
def send_receipts():
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
    gift_collections.send_receipts.apply_async((entries, keys, ), queue=DB_NAME)

    return 'OK'

  except Exception, e:
    logger.error('/send_receipts', exc_info=True)

@app.route('/send_zero_receipt', methods=['POST'])
def send_zero_receipt():
  try:
    arg = request.get_json(force=True)

    html = render_template(
      'email_zero_collection.html',
      first_name = arg['first_name'],
      date = arg['date'],
      address = arg['address'],
      postal = arg['postal'],
      next_pickup = arg['next_pickup']
    )

    r = utils.send_email(arg['email'], 'Your Empties to Winn Pickup', html)
    r = json.loads(r.text)
      
    if r['message'].find('Queued') == 0:
      db['email_status'].insert({
        'account_number': arg['account_number'],
        'recipient': arg["email"], 
        'mid': r['id'], 
        'status':'queued' ,
        'sheet_name': 'Route Importer',
        'worksheet_name': 'Routes',
        "row": arg["row"],
        "upload_status": arg['upload_status']
      })
      logger.info('Queued Zero Collection for ' + arg["email"])

    return 'OK'

  except Exception, e:
    logger.error('/send_zero_receipt', exc_info=True)


@app.route('/send_gift_receipt', methods=['POST'])
def send_gift_receipt():
  try:
    arg = request.get_json(force=True)

    html = render_template(
      'email_collection_receipt.html',
      first_name = arg['first_name'],
      last_date = arg['last_date'],
      last_amount = arg['last_amount'],
      gift_history= arg['gift_history'], 
      next_pickup = arg['next_pickup']
    )

    r = utils.send_email(arg['email'], 'Your Empties to Winn Donation', html)
    
    r = json.loads(r.text)
  
    if r['message'].find('Queued') == 0:
      db['email_status'].insert({
        'account_number': arg['account_number'],
        'recipient': arg['email'], 
        'mid': r['id'], 
        'status':'queued' ,
        'sheet_name': 'Route Importer',
        'worksheet_name': 'Routes',
        "row": arg["row"],
        'upload_status': arg['upload_status']
      })
      #logger.info('inserted record for mid: ' + r['id'])
      logger.info('Queued Collection Receipt for ' + arg['email'])

      return 'OK'

  except Exception, e:
    logger.error('/send_gift_receipt', exc_info=True)

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
      gift_collections.update_entry(db_record)
      
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
