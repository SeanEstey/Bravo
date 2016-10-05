import json
import twilio.twiml
import time
import requests
from datetime import datetime, date
import flask
from flask import Blueprint, request, jsonify, render_template, redirect
from flask.ext.login import login_required, current_user
from bson.objectid import ObjectId
import logging

# Setup Blueprint
main = Blueprint('main', __name__, url_prefix='/')

# Import modules and objects
from app import db, app, socketio
from app import auth
from app import log
from app import utils
from app import routing
from app import wsf
from app import notific_events
from app import pickup_service
from app import receipts
from app import notifications
from app import gsheets
from app import scheduler
from app import etap
from app import notific_events
from app import sms
from app import tasks

# Get logger
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@main.route('/', methods=['GET'])
@login_required
def view_events():

    agency = db['users'].find_one({'user': current_user.username})['agency']

    events = notific_events.get_list(agency)

    for event in events:
        for trigger in event['triggers']:
            t = db['triggers'].find_one({'_id':trigger['id']})
            trigger['type'] = t['type']
            trigger['status'] = t['status']
            trigger['fire_dt'] = t['fire_dt']
            trigger['count'] = db['notifications'].find({'trig_id':trigger['id']}).count()

    return render_template(
      'views/event_list.html',
      title=None,
      events=list(events)
    )

#-------------------------------------------------------------------------------
@main.route('login', methods=['GET','POST'])
def user_login():
    return auth.login()


#-------------------------------------------------------------------------------
@main.route('logout', methods=['GET'])
def user_logout():
    auth.logout()
    return redirect(app.config['PUB_URL'])

#-------------------------------------------------------------------------------
@main.route('/log')
@login_required
def view_log():
    lines = log.get_tail(app.config['LOG_PATH'] + 'info.log', app.config['LOG_LINES'])

    return render_template('views/log.html', lines=lines)

#-------------------------------------------------------------------------------
@main.route('/admin')
@login_required
def view_admin():
    user = db['users'].find_one({'user': current_user.username})
    agency = db['users'].find_one({'user': current_user.username})['agency']

    if user['admin'] == True:
        settings = db['agencies'].find_one({'name':agency}, {'_id':0, 'google.oauth':0})
        settings_html = utils.dict_to_html_table(settings)
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
    routes = routing.get_upcoming_routes(agency)

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

    return json.dumps(routing.get_orders(job_id, api_key))

#-------------------------------------------------------------------------------
@main.route('routing/start_job', methods=['POST'])
def get_routing_job_id():
    logger.info('Routing Block %s...', request.form['block'])

    etap_id = json.loads(request.form['etapestry_id'])

    agency_config = db['agencies'].find_one({
      'name':etap_id['agency']
    })

    try:
        job_id = routing.submit_job(
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
    r = routing.build_route.apply_async(
      args=(route_id,),
      queue=app.config['DB']
    )

    return redirect(app.config['PUB_URL'] + '/routing')

#-------------------------------------------------------------------------------
@main.route('routing/build_sheet/<route_id>/<job_id>', methods=['GET'])
def _build_sheet(job_id, route_id):
    '''non-celery synchronous func for testing
    '''
    routing.build_route(route_id, job_id=job_id)
    return redirect(app.config['PUB_URL'] + '/routing')

#-------------------------------------------------------------------------------
@main.route('reminders/new')
@login_required
def new_event():
    agency = db['users'].find_one({'user': current_user.username})['agency']

    try:
        with open('app/templates/schemas/'+agency+'.json') as json_file:
          templates = json.load(json_file)['reminders']
    except Exception as e:
        logger.error("Couldn't open json schemas file")
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
        logger.error('submit_event: %s', str(e))
        return False

#-------------------------------------------------------------------------------
@main.route('reminders/<event_id>')
@login_required
def view_event(event_id):


    notific_list = db.notifications.aggregate([
        {
            '$match': {
                'event_id': ObjectId(event_id)
            }
        },
        {
            '$group': {
                '_id': '$account.id',
                'results': {
                    '$push': {
                        'status': '$status',
                        'to': '$to',
                        'type': '$type',
                        'account': {
                          'name': '$account.name',
                          'udf': {
                            'status': '$account.udf.status',
                            'block': '$account.udf.block',
                            'pickup_dt': '$account.udf.pickup_date',
                            'driver_notes': '$account.udf.driver_notes',
                            'office_notes': '$account.udf.office_notes'
                          }
                        }
                    }
                }
            }
        }
    ])

    #import bson.json_util
    #logger.info(bson.json_util.dumps(list(notific_list)))


    sort_by = 'name'

    #notific_list = db['notifications'].find({'event_id':ObjectId(event_id)}).sort(sort_by, 1)

    event = db['notification_events'].find_one({'_id':ObjectId(event_id)})
    event['event_dt'] = utils.utc_to_local(event['event_dt'])

    return render_template(
        'views/event.html',
        title=app.config['TITLE'],
        notific_list=list(notific_list),
        event_id=event_id,
        event=event
        #template=job['schema']['import_fields']
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
@main.route('reminders/<job_id>/complete')
@login_required
def job_complete(job_id):
    '''Email job summary, update job status'''

    logger.info('Job [ID %s] complete!', job_id)

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

    tasks.cancel_pickup.apply_async(
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

    logger.info('Record audio request from ' + request.form['To'])

    twilio = db['agencies'].find_one({'name':agency})['twilio']

    call = reminders.dial(
      request.form['To'],
      twilio['ph'],
      twilio['keys']['main'],
      app.config['PUB_URL'] + '/reminders/voice/record/on_answer.xml'
    )

    logger.info('Dial status: %s', call.status)

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

    logger.info('Sending record twimlo response to client')

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

    logger.debug('/reminders/voice/record_on_complete.xml args: %s',
      request.form.to_dict())

    if request.form.get('Digits') == '#':
        record = db['audio'].find_one({'sid': request.form['CallSid']})

        logger.info('Recording completed. Sending audio_url to client')

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
        logger.error('/reminders/voice/play/on_answer.xml: %s', str(e))
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
        logger.error('/reminders/voice/play/on_interact.xml: %s', str(e))
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

    logger.debug(request.form.to_dict())

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

    logger.info('Process receipts request received')

    entries = json.loads(request.form['data'])
    etapestry = json.loads(request.form['etapestry'])

    # Start celery workers to run slow eTapestry API calls
    r = tasks.process_receipts.apply_async(
      args=(entries, etapestry),
      queue=app.config['DB']
    )

    #logger.info('Celery process_receipts task: %s', r.__dict__)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('email/send', methods=['POST'])
def _send_email():
    '''Can be collection receipt from gsheets.process_receipts, reminder email,
    or welcome letter from Google Sheets.
    Required fields: 'agency', 'recipient', 'template', 'subject', and 'data'
    Required fields for updating Google Sheets:
    'data': {'from':{ 'worksheet','row','upload_status'}}
    Returns mailgun_id of email
    '''
    args = request.get_json(force=True)

    logger.debug('/email/send: "%s"', args)

    for key in ['template', 'subject', 'recipient']:
        if key not in args:
            e = '/email/send: missing one or more required fields'
            logger.error(e)
            return flask.Response(response=e, status=500, mimetype='application/json')

    try:
        html = render_template(args['template'], data=args['data'])
    except Exception as e:
        msg = '/email/send: invalid email template'
        logger.error('%s: %s', msg, str(e))
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
        logger.error(str(e))
        return flask.Response(response=e, status=500, mimetype='application/json')

    if r.status_code != 200:
        err = 'Invalid email address "' + args['recipient'] + '": ' + json.loads(r.text)['message']

        logger.error(err)

        gsheets.create_rfu(args['agency'], err)

        return flask.Response(response=str(r), status=500, mimetype='application/json')

    db['emails'].insert({
        'agency': args['agency'],
        'mid': json.loads(r.text)['id'],
        'status': 'queued',
        'on_status': args['data']['from']
    })

    logger.debug('Queued email to ' + args['recipient'])

    return json.loads(r.text)['id']

#-------------------------------------------------------------------------------
@main.route('email/<agency>/unsubscribe', methods=['GET'])
def email_unsubscribe(agency):

    if request.args.get('email'):
        msg = 'Contributor ' + request.args.get('email') + ' has requested to \
              unsubscribe from emails. Please contact to see if they want \
              to cancel the entire service.'

        if agency == 'wsf':
            to = 'emptiestowinn@wsaf.ca'
        elif agency == 'vec':
            to = 'recycle@vecova.ca'

        mailgun = db['agencies'].find_one({})['mailgun']

        try:
            r = requests.post(
              'https://api.mailgun.net/v3/' + 'bravoweb.ca' + '/messages',
              auth=('api', mailgun['api_key']),
              data={
                'from': mailgun['from'],
                'to': to,
                'subject': 'Unsubscribe Request',
                'html': msg
            })
        except requests.exceptions.RequestException as e:
            logger.error(str(e))
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
        logger.error('%s' % request.values.items(), exc_info=True)
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

    logger.info('Email to %s %s',
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
    if email.get('type'):
        if email['type'] == 'notification':
            notifications.on_email_status(request.form.to_dict())
        elif email['type'] == 'receipt':
            receipts.on_email_status(request.form.to_dict())
    # -----------------------------------
    # Signup welcomeor booking confirmation email?
    else:
        try:
            gsheets.update_entry(
              email['agency'],
              request.form['event'],
              email['on_status']
            )
        except Exception as e:
            logger.error("Error writing to Google Sheets: " + str(e))
            return 'Failed'

    #-----------------------------

    # Every email type gets an RFU created

    if event == 'dropped':
        msg = request.form['recipient'] + ' ' + event + ': '

        reason = request.form.get('reason')

        if reason == 'old':
            msg += 'Tried to deliver unsuccessfully for 8 hours'
        elif reason == 'hardfail':
            msg +=  'Can\'t deliver to previous invalid address'

        logger.info(msg)

        tasks.make_rfu.apply_async(
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
    logger.info('NIS!')

    record = request.get_json()

    try:
        gsheets.create_rfu(
          record['custom']['to'] + ' not in service',
          account_number=record['account_id'],
          block=record['custom']['block']
        )
    except Exception, e:
        logger.info('%s /call/nis' % request.values.items(), exc_info=True)
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
        logger.info('/receive_signup: %s', str(e), exc_info=True)
        logger.info('Retrying...')
        wsf.add_signup.apply_async(
          args=(request.form.to_dict(),),
          queue=app.config['DB']
        )
        return str(e)

    return 'OK'


#-------------------------------------------------------------------------------
@main.route('render_receipt', methods=['POST'])
def render_receipt_body():
    try:
        args = request.get_json(force=True)

        return render_template(
          args['template'],
          to = args['data'].get('account').get('email'),
          account = args['data'].get('account'),
          entry = args['data'].get('entry'),
          history = args['data'].get('history'),
          data=args['data'] # remove this after testing
        )
    except Exception as e:
        logger.error('render_receipt: %s ', str(e))
        return 'Error'

#-------------------------------------------------------------------------------
@main.route('render_notification', methods=['POST'])
def render_notification():
    '''Used for notification emails and receipts
    2 args: 'template' html file and 'data'
    Notification emails: 'data' contains ['account' (not etap format), 'to']
    '''

    try:
        args = request.get_json(force=True)

        return render_template(
          args['template'],
          to = args['to'],
          account = args['account']
        )
    except Exception as e:
        logger.error('render_notification: %s ', str(e))
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
    routing.build_todays_routes.apply_async(queue=app.config['DB'])
    return "OK"
