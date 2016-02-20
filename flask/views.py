import json
import mmap
import flask
from datetime import datetime,date, timedelta
from flask import Flask,request,g,Response,url_for, render_template
from flask.ext.login import login_user, logout_user, current_user, login_required

from app import flask_app, db, logger, login_manager
import reminders
import gift_collections
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
  return reminders.view_main()

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

@flask_app.route('/reminders/new')
@login_required
def new_job():
  return flask.render_template('new_job.html', title=TITLE)

@flask_app.route('/reminders/recordaudio', methods=['GET', 'POST'])
def record_msg():
  return reminders.record_audio()

@flask_app.route('/reminders/request/execute/<job_id>')
@login_required
def request_execute_job(job_id):
  job_id = job_id.encode('utf-8')
  # Start celery worker
  reminders.execute_job.apply_async((job_id, ), queue=DB_NAME)

  return 'OK'

@flask_app.route('/collections/send_receipts', methods=['POST'])
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
    logger.error('/collections/send_receipts', exc_info=True)

@flask_app.route('/send_zero_receipt', methods=['POST'])
def send_zero_receipt():
  try:
    arg = request.get_json(force=True)

    html = render_template(
      'email_zero_collection.html',
      email = arg['email'],
      name = arg['name'],
      date = arg['date'],
      address = arg['address'],
      postal = arg['postal'],
      next_pickup = arg['next_pickup']
    )

    r = utils.send_email(arg['email'], 'We missed your pickup this time around', html)
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


@flask_app.route('/send_dropoff_followup', methods=['POST'])
def send_dropoff_followup():
  try:
    arg = request.get_json(force=True)

    html = render_template(
      'email_dropoff_followup.html',
      email = arg['email'],
      name = arg['name'],
      date = arg['date'],
      address = arg['address'],
      postal = arg['postal'],
      next_pickup = arg['next_pickup']
    )

    r = utils.send_email(arg['email'], 'Your Dropoff is Complete', html)
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
      logger.info('Queued Dropoff Followup for ' + arg["email"])

    return 'OK'

  except Exception, e:
    logger.error('/send_zero_receipt', exc_info=True)
@flask_app.route('/send_gift_receipt', methods=['POST'])
def send_gift_receipt():
  try:
    arg = request.get_json(force=True)

    html = render_template(
      'email_collection_receipt.html',
      email = arg['email'],
      name = arg['name'],
      last_date = arg['last_date'],
      last_amount = arg['last_amount'],
      gift_history= arg['gift_history'], 
      next_pickup = arg['next_pickup']
    )

    r = utils.send_email(arg['email'], 'Thanks for your donation!', html)
    
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

@flask_app.route('/send_welcome', methods=['POST'])
def send_welcome_email():
  try:
    if request.method == 'POST':
      args = json.loads(request.form["data"])

      html = render_template(
        'email_welcome.html', 
        first_name = args['first_name'],
        dropoff_date = args["dropoff_date"],
        address = args['address'],
        postal = args['postal']
      )
     
      r = utils.send_email([args['to']], 'Welcome to Empties to Winn', html) 
          
      r = json.loads(r.text)

      if r['message'].find('Queued') == 0:
        db['email_status'].insert({
          'recipient': args['to'], 
          'mid': r['id'], 
          'status':'queued' ,
          'sheet_name': 'Route Importer',
          'worksheet_name': 'Signups',
          "row": args['row'],
          'upload_status': args['upload_status']
        })

        logger.info('Queued welcome letter to ' + args['to'])

      return 'OK'
  except Exception, e:
    logger.error('/send_welcome', exc_info=True)
    return str(e)

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
      gift_collections.create_rfu(request.form['recipient'] + ': received spam complaint')
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
    else:
      logger.info('Email to ' + recipient + ' ' + event)
    
    db['email_status'].update(
      {'mid': mid},
      {'$set': {'status': event}}
    )

    db_record['status'] = event

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

        gift_collections.create_rfu(
            record['imported']['to'] + ' not in service', 
            account_number=record['imported']['account'], 
            block=record['imported']['block']
        )
        
        return False

    except Exception, e:
        logger.info('%s /call/nis' % request.values.items(), exc_info=True)
        return str(e)

@flask_app.route('/receive_signup', methods=['POST'])
def rec_signup():
  try:
      signup = request.form.to_dict()
      logger.info('New signup received: ' + signup['first_name'] + ' ' + signup['last_name'])
      gift_collections.add_signup_row.apply_async((request.form.to_dict(), ), queue=DB_NAME)
      return 'OK'
  except Exception, e:
    logger.info('%s /receive_signup' % request.values.items(), exc_info=True)
    return str(e)
