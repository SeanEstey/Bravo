import json
import twilio.twiml
import flask
import time
import requests
from datetime import datetime,date, timedelta
from flask import Flask,request,g,Response,url_for, render_template
from flask.ext.login import login_user, logout_user, login_required
from bson.objectid import ObjectId

from app import flask_app, db, login_manager, socketio, log_handler
import reminders
import log
import receipts
import gsheets
import scheduler
import auth
import routing
from config import *
import utils

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)

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
      'views/job_list.html',
      title=None,
      jobs=reminders.get_jobs(request.args.values())
    )

#-------------------------------------------------------------------------------
@flask_app.route('/log')
@login_required
def view_log():
    lines = log.get_tail(LOG_FILE, LOG_LINES)

    return flask.render_template('views/log.html', lines=lines)

#-------------------------------------------------------------------------------
@flask_app.route('/admin')
@login_required
def view_admin():
    return flask.render_template('views/admin.html')

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
@flask_app.route('/routing/get_sorted_orders', methods=['POST'])
def get_route():
    logger.info('Routing Block %s', request.form['block'])

    orders = routing.get_sorted_orders(request.form.to_dict())

    return json.dumps(orders)

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/new')
@login_required
def new_job():
    return render_template('views/new_job.html', title=TITLE)

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/submit_job', methods=['POST'])
@login_required
def submit_job():
    try:
        r = reminders.submit_job(request.form.to_dict(), request.files['call_list'])
        return Response(response=json.dumps(r), status=200, mimetype='application/json')
    except Exception as e:
        logger.error('submit_job: %s', str(e))
        return False

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/recordaudio', methods=['GET', 'POST'])
def record_msg():
    return reminders.record_audio()

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>')
@login_required
def view_job(job_id):
    sort_by = 'name'
    reminders = db['reminders'].find({'job_id':ObjectId(job_id)}).sort(sort_by, 1)
    job = db['jobs'].find_one({'_id':ObjectId(job_id)})

    return render_template(
        'views/job.html',
        title=TITLE,
        reminders=reminders,
        job_id=job_id,
        job=job,
        template=job['schema']['import_fields']
    )

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/cancel')
@login_required
def cancel_job(job_id):
    reminders.cancel_job(job_id)
    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/reset')
@login_required
def reset_job(job_id):
    reminders.reset_job(job_id)
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
    reminders.send_calls.apply_async(args=(job_id, ), queue=DB_NAME)
    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/<job_id>/complete')
@login_required
def job_complete(job_id):
    '''Email job summary, update job status'''

    logger.info('Job [ID %s] complete!', job_id)

    # TODO: Send socket to web app to display completed status

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
    try:
        template = reminders.get_call_template(request.values.to_dict())

        html = render_template(
            template['template'],
            reminder=json.loads(reminders.bson_to_json(template['reminder']))
        )

        html = html.replace("\n", "")
        html = html.replace("  ", "")
        logger.info('speak template: %s', html)

        db['reminders'].update({'_id':template['reminder']},{'$set':{'call.speak':html}})

        response = twilio.twiml.Response()
        response.say(html, voice='alice')

        return Response(str(response), mimetype='text/xml')
    except Exception as e:
        logger.info('call.xml: %s', str(e))
        return False

#-------------------------------------------------------------------------------
@flask_app.route('/get_speak', methods=['POST'])
def get_template():
    html = render_template(
        request.form['template'],
        reminder=json.loads(request.form['reminder'])
    )

    return html.replace("\n", "")

#-------------------------------------------------------------------------------
@flask_app.route('/reminders/call_event',methods=['POST','GET'])
def call_event():
    '''Twilio callback'''

    reminders.call_event(request.form.to_dict())
    return 'OK'




#-------------------------------------------------------------------------------
@flask_app.route('/receipts/process', methods=['POST'])
def process_receipts():
    '''Data sent from Routes worksheet in Gift Importer (Google Sheet)
    @arg 'data': JSON array of dict objects with UDF and gift data
    @arg 'keys': JSON dict of etapestry info for PHP script
    '''

    logger.info('Process receipts request received')

    entries = json.loads(request.form['data'])
    keys = json.loads(request.form['keys'])

    # Start celery workers to run slow eTapestry API calls
    r = receipts.process.apply_async(
      args=(entries, keys),
      queue=DB_NAME
    )

    #logger.info('Celery process_receipts task: %s', r.__dict__)

    return 'OK'

#-------------------------------------------------------------------------------
@flask_app.route('/email/send', methods=['POST'])
def send_email():
    '''Can be collection receipt from gsheets.process_receipts, reminder email,
    or welcome letter from Google Sheets.
    Required fields: 'recipient', 'template', 'subject', and 'data'
    Required fields for updating Google Sheets:
    'data': {'from':{ 'worksheet','row','upload_status'}}
    '''

    args = request.get_json(force=True)

    for key in ['template', 'subject', 'recipient']:
        if key not in args:
            e = '/email/send: missing one or more required fields'
            logger.error(e)
            return Response(response=e, status=500, mimetype='application/json')

    try:
        html = render_template(args['template'], data=args['data'])
    except Exception as e:
        msg = '/email/send: invalid email template'
        logger.error('%s: %s', msg, str(e))
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
    Guaranteed POST data: 'event', 'recipient', 'Message-Id'
    event param can be: 'delivered', 'bounced', or 'dropped'
    Optional POST data: 'code' (on dropped/bounced), 'error' (on bounced),
    'reason' (on dropped)
    '''

    logger.info('Email to %s %s',
      request.form['recipient'], request.form['event']
    )

    event = request.form['event']
    if event == 'dropped':
        gsheets.create_rfu.apply_async(
            args=(request.form['recipient'] + ' ' + event, ),
            queue=DB_NAME)

    db_doc = db['emails'].find_one_and_update(
      {'mid': request.form['Message-Id']},
      {'$set': { 'status': request.form['event']}}
    )

    if db_doc is None or 'on_status_update' not in db_doc:
        return 'No record to update'

    if 'worksheet' in db_doc['on_status_update']:
        # Update Google Sheets
        try:
            gsheets.update_entry(
              request.form['event'],
              db_doc['on_status_update']
            )
        except Exception as e:
            logger.error("Error writing to Google Sheets: " + str(e))
            return 'Failed'

    elif 'reminder_id' in db_doc['on_status_update']:
        # Update Reminder record
        db['reminders'].update_one(
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
    '''Forwarded signup submision from emptiestowinn.com
    Adds signup data to Route Importer->Signups gsheet row
    '''

    logger.info('New signup received: %s %s',
      request.form.get('first_name'),
      request.form.get('last_name')
    )

    try:
        gsheets.add_signup.apply_async(
          args=(request.form.to_dict(),), # Must include comma
          queue=DB_NAME
        )
    except Exception as e:
        time.sleep(1)
        logger.info('/receive_signup: %s', str(e), exc_info=True)
        logger.info('Retrying...')
        gsheets.add_signup.apply_async(
          args=(request.form.to_dict(),),
          queue=DB_NAME
        )
        return str(e)

    return 'OK'
