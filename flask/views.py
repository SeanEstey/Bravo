import json
import flask
import time
import requests
from datetime import datetime,date, timedelta
from flask import Flask,request,g,Response,url_for, render_template
from flask.ext.login import login_user, logout_user, login_required
from bson.objectid import ObjectId

from app import flask_app, db, logger, login_manager, socketio
import reminders
import log
import receipts
import gsheets
import scheduler
import auth
from config import *
import utils

#-------------------------------------------------------------------------------
@flask_app.before_request
def before_request():
    g.user = flask.ext.login.current_user

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
    lines = log.get_tail(LOG_FILE, 50)
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
def no_pickup(msg_id):
    '''Script run via reminder email'''

    reminders.cancel_pickup.apply_async((msg_id,), queue=DB_NAME)
    return 'Thank You'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/call.xml',methods=['POST'])
def call_xml():
    '''Twilio TwiML Voice Request'''
    response = reminders.get_call_xml(request.values.to_dict())
    return Response(str(response), mimetype='text/xml')

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/call_event',methods=['POST','GET'])
def call_event():
    '''Twilio callback'''

    reminders.call_event(request.form.to_dict())
    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/collections/process_receipts', methods=['POST'])
def process_receipts():
    '''Data sent from Routes worksheet in Gift Importer (Google Sheet)
    @arg 'data': JSON array of dict objects with UDF and gift data
    @arg 'keys': JSON dict of etapestry info for PHP script
    '''

    entries = json.loads(request.form['data'])
    keys = json.loads(request.form['keys'])

    # Start celery workers to run slow eTapestry API calls
    r = receipts.process.apply_async(
      args=(entries, keys),
      queue=DB_NAME
    )

    logger.info('Celery process_receipts task: %s', r.__dict__)

    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/email/send', methods=['POST'])
def send_email():
    '''Can be collection receipt from gsheets.process_receipts, reminder email,
    or welcome letter from Google Sheets.
    Required fields: 'recipient', 'template', 'subject', and 'data'
    Required fields for updating Google Sheets: 'data': {'from':{'sheet_name',
    'worksheet_name', 'row', 'upload_status'}}
    '''

    args = request.get_json(force=True)

    logger.info(args)

    for key in ['template', 'subject', 'recipient']:
        if key not in args:
            e = '/email/send: missing one or more required fields'
            logger.error(e)
            return Response(response=e, status=500, mimetype='application/json')

    try:
        html = render_template(args['template'], data=args['data'])
    except Exception, e:
        e = '/email/send: invalid email template'
        logger.error(e)
        return Response(response=e, status=500, mimetype='application/json')

    try:
        r = requests.post(
          'https://api.mailgun.net/v3/' + MAILGUN_DOMAIN + '/messages',
          auth=('api', MAILGUN_API_KEY),
          data={
            'from': FROM_EMAIL,
            'to': args['recipient'],
            'subject': args['subject'],
            'html': html
        })
    except requests.exceptions.RequestException as e:
        logger.error(str(e))
        return Response(response=e, status=500, mimetype='application/json')

    if r.status_code != 200:
        e = '/email/send: mailgun error: ' + r.text
        logger.error(e)
        return Response(response=e, status=500, mimetype='application/json')

    db['emails'].insert({
        'mid': json.loads(r.text)['id'],
        'status': 'queued',
        'on_status_update': args['data']['from']
    })

    logger.info('Queued email to ' + args['recipient'])

    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/email/unsubscribe', methods=['GET'])
def email_unsubscribe():
    if request.args.get('email'):
        msg = 'Contributor ' + request.args['email'] + ' has requested to \
              unsubscribe from ETW emails. Please contact to see if they want \
              to cancel the entire service.'

        utils.send_email(['emptiestowinn@wsaf.ca'], 'Unsubscribe request', msg)

        return 'We have received your request to unsubscribe ' \
                + request.args['email'] + ' from Empties to Winn. If you wish \
                to cancel the service, please allow us to contact you once \
                more to arrange for retrieval of the Bag Buddy or other \
                collection materials provided to you. As a non-profit, \
                this allows us to spread out our costs.'
    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/email/spam_complaint', methods=['POST'])
def email_spam_complaint():
    m = 'received spam complaint'

    try:
        gsheets.create_rfu(request.form['recipient'] + m)
    except Exception, e:
        logger.error('%s' % request.values.items(), exc_info=True)
        return str(e)

    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/email/status',methods=['POST'])
def email_status():
    '''Relay for Mailgun webhooks. Can originate from reminder_msg, Signups
    sheet, or Route Importer sheet
    Guaranteed POST data: 'event', 'recipient', 'Message-Id',
    Optional POST data: 'code' (on dropped/bounced), 'error' (on bounced),
    'reason' (on dropped)
    Where event can be: 'delivered', 'bounced', or 'dropped'
    '''

    logger.info('Email to %s %s',
      request.form['recipient'], request.form['event']
    )

    db_doc = db['emails'].find_one({'mid': request.form['Message-Id']})

    if db_doc is None:
        return 'OK'

    if 'on_status_update' not in db_doc:
        return 'OK'

    # Do any required follow-up actions

    # Google Sheets?
    if 'sheet_name' in db_doc['on_status_update']:
        try:
            gsheets.update_entry(db_doc['on_status_update'])
        except Exception as e:
            logger.error("Error writing to Google Sheets: " + str(e))
            return 'failed'
    # Reminder email?
    elif 'reminder_msg_id' in db_doc['on_status_update']:
        db['reminder_msgs'].update_one(
          {'email.mid': request.form['Message-Id']},
          {'$set':{
            "email.status": request.form['event'],
            "email.code": request.form.get('code'),
            "email.reason": request.form.get('reason'),
            "email.error": request.form.get('error')
          }}
        )

    #socketio.emit('update_msg', {'id':str(msg['_id']), 'emails': request.form['event']})

    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/get_np', methods=['GET'])
def get_romorrow_accounts():
    scheduler.find_nps_in_schedule.apply_async(queue=DB_NAME)
    return 'Celery process started...'

#-------------------------------------------------------------------------------
@flask_app.route('/call/nis', methods=['POST'])
def nis():
    logger.info('NIS!')

    record = request.get_json()

    try:
        gsheets.create_rfu(
          record['imported']['to'] + ' not in service',
          account_number=record['imported']['account'],
          block=record['imported']['block']
        )
    except Exception, e:
        logger.info('%s /call/nis' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
@flask_app.route('/receive_signup', methods=['POST'])
def rec_signup():
    """Forwarded signup submision from emptiestowinn.com
    Adds signup data to Route Importer->Signups gsheet row"""

    logger.info('New signup received: %s %s',
      request.form.get('first_name'),
      request.form.get('last_name')
    )

    try:
        gsheets.add_signup_row.apply_async(
          args=(request.form.to_dict()),
          queue=DB_NAME
        )
    except Exception as e:
        time.sleep(1)
        logger.info('/receive_signup: %s', str(e), exc_info=True)
        logger.info('Retrying...')
        gsheets.add_signup_row.apply_async(
          args=(request.form.to_dict()),
          queue=DB_NAME
        )
        return str(e)

    return 'OK'
