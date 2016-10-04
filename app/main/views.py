import json
import twilio.twiml
import time
import requests
from datetime import datetime,date
import flask
from flask import Blueprint, request, jsonify, render_template, redirect
from flask.ext.login import login_required, current_user
from bson.objectid import ObjectId
import pytz
import logging

# Import Application objects
from app import db, socketio

main = Blueprint('main', __name__, url_prefix='/')

# Import methods
from app.utils import send_email, dict_to_html_table
import app.wsf
from app.log import get_tail
from app.auth import login, logout
from app.routing import get_orders,submit_job,build_route,get_upcoming_routes,build_todays_routes
import app.notific_events
import app.pickup_service
#import app.tasks
import app.receipts
import app.notifications
import app.gsheets
import app.scheduler
import app.etap
import app.sms

from app import db, info_handler, error_handler, debug_handler, login_manager

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(debug_handler)
logger.setLevel(logging.DEBUG)


#-------------------------------------------------------------------------------
@main.route('/', methods=['GET'])
#@login_required
def view_events():

    #agency = db['users'].find_one({'user': current_user.username})['agency']
    #events = notific_events.get_list(agency)

    return render_template(
      'views/event_list.html',
      title=None
      #events=events
    )

#-------------------------------------------------------------------------------
@main.route('login', methods=['GET','POST'])
def user_login():
    return login()


#-------------------------------------------------------------------------------
@main.route('logout', methods=['GET'])
def user_logout():
    logout()
    return redirect(app.config['PUB_URL'])

#-------------------------------------------------------------------------------
@main.route('/log')
@login_required
def view_log():
    lines = get_tail(app.config['LOG_PATH'] + 'info.log', app.config['LOG_LINES'])

    return render_template('views/log.html', lines=lines)

#-------------------------------------------------------------------------------
@main.route('/admin')
@login_required
def view_admin():
    user = db['users'].find_one({'user': current_user.username})
    agency = db['users'].find_one({'user': current_user.username})['agency']

    if user['admin'] == True:
        settings = db['agencies'].find_one({'name':agency}, {'_id':0, 'google.oauth':0})
        settings_html = dict_to_html_table(settings)
    else:
        settings_html = ''

    return render_template('views/admin.html', agency_config=settings_html)


#-------------------------------------------------------------------------------
@main.route('sendsocket', methods=['GET'])
def request_send_socket():
    name = request.args.get('name').encode('utf-8')
    data = request.args.get('data').encode('utf-8')
    socketio.emit(name, data)
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('booking', methods=['GET'])
@login_required
def show_booking():
    agency = db['users'].find_one({'user': current_user.username})['agency']
    return render_template('views/booking.html', agency=agency)

#-------------------------------------------------------------------------------
@main.route('routing', methods=['GET'])
@login_required
def show_routing():
    agency = db['users'].find_one({'user': current_user.username})['agency']
    agency_conf = db['agencies'].find_one({'name':agency})
    routes = get_upcoming_routes(agency)

    return render_template(
      'views/routing.html',
      routes=routes,
      depots=agency_conf['routing']['depots'],
      drivers=agency_conf['routing']['drivers']
    )

#-------------------------------------------------------------------------------
@main.route('routing/get_scheduled_route', methods=['POST'])
def get_today_route():
    return True
    '''return json.dumps(get_scheduled_route(
      etapestry_id['agency'],
      request.form['block'],
      request.form['date']))
    '''

#-------------------------------------------------------------------------------
@main.route('routing/get_route/<job_id>', methods=['GET'])
def get_route(job_id):
    agency = db['routes'].find_one({'job_id':job_id})['agency']
    conf = db['agencies'].find_one({'name':agency})
    api_key = conf['google']['geocode']['api_key']

    return json.dumps(get_orders(job_id, api_key))

#-------------------------------------------------------------------------------
@main.route('routing/start_job', methods=['POST'])
def get_routing_job_id():
    app.logger.info('Routing Block %s...', request.form['block'])

    etap_id = json.loads(request.form['etapestry_id'])

    agency_config = db['agencies'].find_one({
      'name':etap_id['agency']
    })

    try:
        job_id = submit_job(
          request.form['block'],
          request.form['driver'],
          request.form['date'],
          request.form['start_address'],
          request.form['end_address'],
          etap_id,
          agency_config['routing']['routific']['api_key'],
          min_per_stop=request.form['min_per_stop'],
          shift_start=request.form['shift_start'])
    except Exception as e:
        logger.error(str(e))
        return False

    return job_id

#-------------------------------------------------------------------------------
@main.route('routing/build/<route_id>', methods=['GET', 'POST'])
def _build_route(route_id):
    r = build_route.apply_async(
      args=(route_id,),
      queue=app.config['DB']
    )

    return redirect(app.config['PUB_URL'] + '/routing')

#-------------------------------------------------------------------------------
@main.route('routing/build_sheet/<route_id>/<job_id>', methods=['GET'])
def _build_sheet(job_id, route_id):
    '''non-celery synchronous func for testing
    '''
    build_route(route_id, job_id=job_id)
    return redirect(app.config['PUB_URL'] + '/routing')

#-------------------------------------------------------------------------------
@main.route('reminders/new')
@login_required
def new_event():
    agency = db['users'].find_one({'user': current_user.username})['agency']

    try:
        with open('templates/schemas/'+agency+'.json') as json_file:
          templates = json.load(json_file)['reminders']
    except Exception as e:
        app.logger.error("Couldn't open json schemas file")
        return "Error"

    return render_template('views/new_event.html', templates=templates, title=app.config['TITLE'])

#-------------------------------------------------------------------------------
@main.route('reminders/submit_event', methods=['POST'])
@login_required
def _submit_event():
    try:
        r = reminders.submit_event(request.form.to_dict(), request.files['call_list'])
        return flask.Response(response=json.dumps(r), status=200, mimetype='application/json')
    except Exception as e:
        app.logger.error('submit_event: %s', str(e))
        return False

#-------------------------------------------------------------------------------
@main.route('reminders/<event_id>')
@login_required
def view_event(event_id):
    sort_by = 'name'

    notific_list = db['notifications'].find({'event_id':ObjectId(event_id)}).sort(sort_by, 1)

    event = db['events'].find_one({'_id':ObjectId(event_id)})

    local = pytz.timezone("Canada/Mountain")
    job['voice']['fire_at'] = job['voice']['fire_at'].replace(tzinfo=pytz.utc).astimezone(local)

    return render_template(
        'views/event.html',
        title=app.config['TITLE'],
        reminders=reminders,
        job_id=job_id,
        job=job,
        template=job['schema']['import_fields']
    )

#-------------------------------------------------------------------------------
@main.route('reminders/<event_id>/cancel')
@login_required
def cancel_event(event_id):
    reminders.cancel_event(event_id)
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('reminders/<event_id>/reset')
@login_required
def reset_event(event_id):
    reminders.reset_event(event_id)
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('reminders/<event_id>/send_emails')
@login_required
def send_emails(event_id):
    reminders.send_emails.apply_async(
            (event_id.encode('utf-8'),),
            queue=app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('reminders/<event_id>/send_calls')
@login_required
def send_calls(event_id):
    event_id = event_id.encode('utf-8')

    # Start new event
    db['events'].update_one(
      {'_id': ObjectId(job_id)},
      {'$set': {
        "status": "in-progress",
        "voice.started_at": datetime.now()}})

    reminders.send_calls.apply_async(
            args=(job_id, ),
            queue=app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('reminders/<job_id>/complete')
@login_required
def job_complete(job_id):
    '''Email job summary, update job status'''

    app.logger.info('Job [ID %s] complete!', job_id)

    # TODO: Send socket to web app to display completed status

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('reminders/<job_id>/<reminder_id>/remove', methods=['POST'])
@login_required
def rmv_msg(job_id, reminder_id):
    reminders.rmv_msg(job_id, reminder_id)
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('reminders/<reminder_id>/edit', methods=['POST'])
@login_required
def edit_msg(reminder_id):
    reminders.edit_msg(reminder_id, request.form.items())
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('reminders/<event_id>/<account_id>/cancel_pickup', methods=['GET'])
def no_pickup(event_id, account_id):
    '''Script run via reminder email'''

    app.tasks.cancel_pickup.apply_async(
        (event_id, account_id),
        queue=app.config['DB'])

    return 'Thank You'

#-------------------------------------------------------------------------------
@main.route('reminders/play/sample', methods=['POST'])
def play_sample_rem():
    voice = twilio.twiml.Response()
    voice.say("test")
    return flask.Response(response=str(voice), mimetype='text/xml')


#-------------------------------------------------------------------------------
@main.route('reminders/get/token', methods=['GET'])
def get_twilio_token():
    # get credentials for environment variables

    import re
    from twilio.util import TwilioCapability

    # FIXME
    twilio = db['agencies'].find_one({'name':'vec'})['twilio']['keys']['main']
    alphanumeric_only = re.compile('[\W_]+')
    # Generate a random user name
    #identity = alphanumeric_only.sub('', "sean")

    # Create a Capability Token
    capability = TwilioCapability(twilio['sid'], twilio['auth_id'])
    capability.allow_client_outgoing(twilio['app_sid'])
    capability.allow_client_incoming("sean")
    token = capability.generate()

    # Return token info as JSON
    return jsonify(identity="sean", token=token)


#-------------------------------------------------------------------------------
@main.route('reminders/voice/record/request', methods=['POST'])
def record_msg():
    '''Request: POST from Bravo javascript client with 'To' arg
    Response: JSON dict {'status':'string'}
    '''

    agency = db['users'].find_one({'user': current_user.username})['agency']

    app.logger.info('Record audio request from ' + request.form['To'])

    twilio = db['agencies'].find_one({'name':agency})['twilio']

    call = reminders.dial(
      request.form['To'],
      twilio['ph'],
      twilio['keys']['main'],
      app.config['PUB_URL'] + '/reminders/voice/record/on_answer.xml'
    )

    app.logger.info('Dial status: %s', call.status)

    if call.status == 'queued':
        doc = {
            'date': datetime.utcnow(),
            'sid': call.sid,
            'agency': agency,
            'to': call.to,
            'from': call.from_,
            'status': call.status,
            'direction': call.direction
        }

        db['audio'].insert_one(doc)

    return flask.Response(response=json.dumps({'status':call.status}), mimetype='text/xml')


#-------------------------------------------------------------------------------
@main.route('reminders/voice/record/on_answer.xml',methods=['POST'])
def record_xml():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    app.logger.info('Sending record twimlo response to client')

    # Record voice message
    voice = twilio.twiml.Response()
    voice.say('Record your message after the beep. Press pound when complete.',
      voice='alice'
    )
    voice.record(
        method= 'POST',
        action= app.config['PUB_URL'] + '/reminders/voice/record/on_complete.xml',
        playBeep= True,
        finishOnKey='#'
    )

    #send_socket('record_audio', {'msg': 'Listen to the call for instructions'})

    return flask.Response(response=str(voice), mimetype='text/xml')

#-------------------------------------------------------------------------------
@main.route('reminders/voice/record/on_complete.xml', methods=['POST'])
def record_complete_xml():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    app.logger.debug('/reminders/voice/record_on_complete.xml args: %s',
      request.form.to_dict())

    if request.form.get('Digits') == '#':
        record = db['audio'].find_one({'sid': request.form['CallSid']})

        app.logger.info('Recording completed. Sending audio_url to client')

        # Reminder job has not been created yet so save in 'audio' for now

        db['audio'].update_one(
          {'sid': request.form['CallSid']},
          {'$set': {
              'audio_url': request.form['RecordingUrl'],
              'audio_duration': request.form['RecordingDuration'],
              'status': 'completed'
        }})

        socketio.emit('record_audio', {'audio_url': request.form['RecordingUrl']})

        voice = twilio.twiml.Response()
        voice.say('Message recorded. Goodbye.', voice='alice')
        voice.hangup()

    return flask.Response(response=str(voice), mimetype='text/xml')


#-------------------------------------------------------------------------------
@main.route('reminders/voice/play/on_answer.xml',methods=['POST'])
def get_answer_xml():
    '''Reminder call is answered.
    Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    try:
        voice = notifications.get_voice_play_answer_response(request.form.to_dict())
    except Exception as e:
        app.logger.error('/reminders/voice/play/on_answer.xml: %s', str(e))
        return flask.Response(response="Error", status=500, mimetype='text/xml')

    return flask.Response(response=str(voice), mimetype='text/xml')


#-------------------------------------------------------------------------------
@main.route('reminders/voice/play/on_interact.xml', methods=['POST'])
def get_interact_xml():
    '''User interacted with reminder call. Send voice response.
    Request: Twilio POST
    Response: twilio.twiml.Response
    '''

    try:
        voice = notifications.get_voice_play_interact_response(request.form.to_dict())
    except Exception as e:
        app.logger.error('/reminders/voice/play/on_interact.xml: %s', str(e))
        return flask.Response(response="Error", status=500, mimetype='text/xml')

    return flask.Response(response=str(voice), mimetype='text/xml')


#-------------------------------------------------------------------------------
@main.route('reminders/voice/on_complete',methods=['POST'])
def call_event():
    '''Twilio callback'''

    notifications.call_event(request.form.to_dict())
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('sms/status', methods=['POST'])
def sms_status():
    '''Callback for sending/receiving SMS messages.
    If sending, determine if part of reminder or reply to original received msg
    '''

    app.logger.debug(request.form.to_dict())

    doc = db['sms'].find_one_and_update(
      {'SmsSid': request.form['SmsSid']},
      {'$set': { 'SmsStatus': request.form['SmsStatus']}}
    )

    if not doc:
        db['sms'].insert_one(request.form.to_dict())

    if request.form['SmsStatus'] == 'received':
        sms.do_request(
          request.form['To'],
          request.form['From'],
          request.form['Body'],
          request.form['SmsSid'])

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('receipts/process', methods=['POST'])
def process_receipts():
    '''Data sent from Routes worksheet in Gift Importer (Google Sheet)
    @arg 'data': JSON array of dict objects with UDF and gift data
    @arg 'etapestry': JSON dict of etapestry info for PHP script
    '''

    app.logger.info('Process receipts request received')

    entries = json.loads(request.form['data'])
    etapestry = json.loads(request.form['etapestry'])

    # Start celery workers to run slow eTapestry API calls
    r = app.tasks.process_receipts.apply_async(
      args=(entries, etapestry),
      queue=app.config['DB']
    )

    #app.logger.info('Celery process_receipts task: %s', r.__dict__)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('email/send', methods=['POST'])
def send_email():
    '''Can be collection receipt from gsheets.process_receipts, reminder email,
    or welcome letter from Google Sheets.
    Required fields: 'agency', 'recipient', 'template', 'subject', and 'data'
    Required fields for updating Google Sheets:
    'data': {'from':{ 'worksheet','row','upload_status'}}
    Returns mailgun_id of email
    '''
    args = request.get_json(force=True)

    app.logger.debug('/email/send: "%s"', args)

    for key in ['template', 'subject', 'recipient']:
        if key not in args:
            e = '/email/send: missing one or more required fields'
            app.logger.error(e)
            return flask.Response(response=e, status=500, mimetype='application/json')

    try:
        html = render_template(args['template'], data=args['data'])
    except Exception as e:
        msg = '/email/send: invalid email template'
        app.logger.error('%s: %s', msg, str(e))
        return flask.Response(response=e, status=500, mimetype='application/json')

    mailgun = db['agencies'].find_one({'name':args['agency']})['mailgun']

    try:
        r = requests.post(
          'https://api.mailgun.net/v3/' + mailgun['domain'] + '/messages',
          auth=('api', mailgun['api_key']),
          data={
            'from': mailgun['from'],
            'to': args['recipient'],
            'subject': args['subject'],
            'html': html
        })
    except requests.exceptions.RequestException as e:
        app.logger.error(str(e))
        return flask.Response(response=e, status=500, mimetype='application/json')

    if r.status_code != 200:
        err = 'Invalid email address "' + args['recipient'] + '": ' + json.loads(r.text)['message']

        app.logger.error(err)

        gsheets.create_rfu(args['agency'], err)

        return flask.Response(response=str(r), status=500, mimetype='application/json')

    db['emails'].insert({
        'agency': args['agency'],
        'mid': json.loads(r.text)['id'],
        'status': 'queued',
        'on_status_update': args['data']['from']
    })

    app.logger.debug('Queued email to ' + args['recipient'])

    return json.loads(r.text)['id']

#-------------------------------------------------------------------------------
@main.route('email/unsubscribe', methods=['GET'])
def email_unsubscribe():
    if request.args.get('email'):
        msg = 'Contributor ' + request.args.get('email') + ' has requested to \
              unsubscribe from emails. Please contact to see if they want \
              to cancel the entire service.'

        mailgun = db['agencies'].find_one({})['mailgun']

        try:
            r = requests.post(
              'https://api.mailgun.net/v3/' + 'bravoweb.ca' + '/messages',
              auth=('api', mailgun['api_key']),
              data={
                'from': mailgun['from'],
                'to': ['sestey@vecova.ca', 'emptiestowinn@wsaf.ca'],
                'subject': 'Unsubscribe Request',
                'html': msg
            })
        except requests.exceptions.RequestException as e:
            app.logger.error(str(e))
            return flask.Response(response=e, status=500, mimetype='application/json')

        return 'We have received your request to unsubscribe ' \
                + request.args.get('email') + ' If you wish \
                to cancel the service, please allow us to contact you once \
                more to arrange for retrieval of the Bag Buddy or other \
                collection materials provided to you. As a non-profit, \
                this allows us to spread out our costs.'
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/spam_complaint', methods=['POST'])
def email_spam_complaint():
    m = 'received spam complaint'

    try:
        gsheets.create_rfu(request.form['recipient'] + m)
    except Exception, e:
        app.logger.error('%s' % request.values.items(), exc_info=True)
        return str(e)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('email/status',methods=['POST'])
def email_status():
    '''Relay for Mailgun webhooks. Can originate from reminder_msg, Signups
    sheet, or Route Importer sheet
    Guaranteed POST data: 'event', 'recipient', 'Message-Id'
    event param can be: 'delivered', 'bounced', or 'dropped'
    Optional POST data: 'code' (on dropped/bounced), 'error' (on bounced),
    'reason' (on dropped)
    '''

    app.logger.info('Email to %s %s',
      request.form['recipient'], request.form['event']
    )

    event = request.form['event']

    email = db['emails'].find_one_and_update(
      {'mid': request.form['Message-Id']},
      {'$set': { 'status': request.form['event']}}
    )

    if email is None:
        return 'Mid not found'

    #------------- NEW CODE----------------

    # Do any special updates

    if email['type'] == 'notification':
        notifications.on_email_status(request.form.to_dict())
    elif email['type'] == 'receipt':
        receipts.on_email_status(request.form.to_dict())

    #-----------------------------

    # Every email type gets an RFU created

    if event == 'dropped':
        msg = request.form['recipient'] + ' ' + event + ': '

        reason = request.form.get('reason')

        if reason == 'old':
            msg += 'Tried to deliver unsuccessfully for 8 hours'
        elif reason == 'hardfail':
            msg +=  'Can\'t deliver to previous invalid address'

        app.logger.info(msg)

        app.tasks.make_rfu.apply_async(
            args=(email['agency'], msg, ),
            queue=app.config['DB'])

    #socketio.emit('update_msg', {'id':str(msg['_id']), 'emails': request.form['event']})

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('get_np', methods=['GET'])
def get_romorrow_accounts():
    scheduler.find_nps_in_schedule.apply_async(queue=app.config['DB'])
    return 'Celery process started...'

#-------------------------------------------------------------------------------
@main.route('call/nis', methods=['POST'])
def nis():
    app.logger.info('NIS!')

    record = request.get_json()

    try:
        gsheets.create_rfu(
          record['custom']['to'] + ' not in service',
          account_number=record['account_id'],
          block=record['custom']['block']
        )
    except Exception, e:
        app.logger.info('%s /call/nis' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
@main.route('receive_signup', methods=['POST'])
def rec_signup():
    '''Forwarded signup submision from emptiestowinn.com
    Adds signup data to Bravo Sheets->Signups gsheet row
    '''

    try:
        wsf.add_signup.apply_async(
          args=(request.form.to_dict(),), # Must include comma
          queue=app.config['DB']
        )
    except Exception as e:
        time.sleep(1)
        app.logger.info('/receive_signup: %s', str(e), exc_info=True)
        app.logger.info('Retrying...')
        wsf.add_signup.apply_async(
          args=(request.form.to_dict(),),
          queue=app.config['DB']
        )
        return str(e)

    return 'OK'


#-------------------------------------------------------------------------------
@main.route('render_html', methods=['POST'])
def _render_html():
    '''2 args: 'template' html file and data
    Can be called to render reminder emails or receipt emails
    '''

    try:
        args = request.get_json(force=True)
        data = args['data']

        app.logger.debug('view: render_html')

        return render_template(
          args['template'],
          account = data.get('account') or None,
          entry = data.get('entry') or None,
          to = data.get('to') or None,
          data=args['data'] # remove this after testing
        )
    except Exception as e:
        app.logger.error('render_html: %s ', str(e))
        return 'Error'


#-----------------------TEST VIEWS-----------------------------------------------

@main.route('set_rem', methods=['GET'])
def set_reminders():
    scheduler.setup_reminder_jobs()
    return 'OK'

@main.route('get_nps',methods=['GET'])
def get_the_nps():
    scheduler.analyze_non_participants()
    return "OK"

@main.route('test_build_routes',methods=['GET'])
def test_build_routes():
    build_todays_routes.apply_async(queue=app.config['DB'])
    return "OK"
