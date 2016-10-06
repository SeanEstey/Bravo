# notify view
import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import \
    Blueprint, request, jsonify, \
    render_template, redirect, Response
from flask.ext.login import login_required, current_user
from bson.objectid import ObjectId
import logging

notify = Blueprint('notify', __name__, url_prefix='/notify')

# Import modules and objects

from app import utils
from app import sms
from app import tasks
from app.notify import notific_events
from app.notify import triggers
from app.notify import notifications
from app.notify import pickup_service

from app import db, app, socketio

# Get logger
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@notify.route('/', methods=['GET'])
@login_required
def view_event_list():

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
@notify.route('/new')
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
@notify.route('/submit_event', methods=['POST'])
@login_required
def _submit_event():
    try:
        r = reminders.submit_event(request.form.to_dict(), request.files['call_list'])
        return Response(response=json.dumps(r), status=200, mimetype='application/json')
    except Exception as e:
        logger.error('submit_event: %s', str(e))
        return False

#-------------------------------------------------------------------------------
@notify.route('/<event_id>')
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
                            'pickup_dt': '$account.udf.pickup_dt',
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
    #logger.debug(bson.json_util.dumps(notific_list))

    #logger.info(bson.json_util.dumps(list(notific_list)))


    sort_by = 'name'

    #notific_list = db['notifications'].find({'event_id':ObjectId(event_id)}).sort(sort_by, 1)

    event = db['notification_events'].find_one({'_id':ObjectId(event_id)})
    event['event_dt'] = utils.utc_to_local(event['event_dt'])

    triggers = []
    for trigger in event['triggers']:
        t = db['triggers'].find_one({'_id':trigger['id']})
        t['_id'] = str(t['_id'])
        triggers.append(t)

    return render_template(
        'views/event.html',
        title=app.config['TITLE'],
        notific_list=list(notific_list),
        event_id=event_id,
        event=event,
        triggers=triggers
        #template=job['schema']['import_fields']
    )

#-------------------------------------------------------------------------------
@notify.route('/<event_id>/cancel')
@login_required
def cancel_event(event_id):
    reminders.cancel_event(event_id)
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<event_id>/reset')
@login_required
def reset_event(event_id):
    notific_events.reset(event_id)
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<event_id>/complete')
@login_required
def job_complete(event_id):
    '''Email job summary, update job status'''

    logger.info('Job [ID %s] complete!', event_id)

    # TODO: Send socket to web app to display completed status

    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<event_id>/<notific_id>/remove', methods=['POST'])
@login_required
def rmv_msg(event_id, notific_id):
    reminders.rmv_msg(event_id, notific_id)
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<notific_id>/edit', methods=['POST'])
@login_required
def edit_msg(notific_id):
    reminders.edit_msg(notific_id, request.form.items())
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<trigger_id>/fire', methods=['POST'])
@login_required
def fire_trigger(trigger_id):
    trigger = db['triggers'].find_one({'_id':ObjectId(trigger_id)})
    tasks.fire_trigger.apply_async(
            (str(trigger['event_id']), trigger_id),
            queue=app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<event_id>/<account_id>/no_pickup', methods=['GET'])
def no_pickup(event_id, account_id):
    '''Script run via reminder email'''

    tasks.cancel_pickup.apply_async(
        (event_id, account_id),
        queue=app.config['DB'])

    return 'Thank You'

#-------------------------------------------------------------------------------
@notify.route('/play/sample', methods=['POST'])
def play_sample_rem():
    voice = twilio.twiml.Response()
    voice.say("test")
    return Response(response=str(voice), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/get/token', methods=['GET'])
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
@notify.route('/voice/record/request', methods=['POST'])
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
      app.config['PUB_URL'] + '/voice/record/on_answer.xml'
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

    return Response(response=json.dumps({'status':call.status}), mimetype='text/xml')


#-------------------------------------------------------------------------------
@notify.route('/voice/record/on_answer.xml',methods=['POST'])
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
        action= app.config['PUB_URL'] + '/voice/record/on_complete.xml',
        playBeep= True,
        finishOnKey='#'
    )

    #send_socket('record_audio', {'msg': 'Listen to the call for instructions'})

    return Response(response=str(voice), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/record/on_complete.xml', methods=['POST'])
def record_complete_xml():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    logger.debug('/voice/record_on_complete.xml args: %s',
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

    return Response(response=str(voice), mimetype='text/xml')


#-------------------------------------------------------------------------------
@notify.route('/voice/play/on_answer.xml',methods=['POST'])
def get_answer_xml():
    '''Reminder call is answered.
    Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    try:
        voice = notifications.on_call_answered(request.form.to_dict())
    except Exception as e:
        logger.error('/voice/play/on_answer.xml: %s', str(e))
        return Response(response="Error", status=500, mimetype='text/xml')

    return Response(response=str(voice), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/play/on_interact.xml', methods=['POST'])
def get_interact_xml():
    '''User interacted with reminder call. Send voice response.
    Request: Twilio POST
    Response: twilio.twiml.Response
    '''

    try:
        voice = notifications.on_call_interact(request.form.to_dict())
    except Exception as e:
        logger.error('/voice/play/on_interact.xml: %s', str(e))
        return Response(response="Error", status=500, mimetype='text/xml')

    return Response(response=str(voice), mimetype='text/xml')


#-------------------------------------------------------------------------------
@notify.route('/voice/on_complete',methods=['POST'])
def call_event():
    '''Twilio callback'''

    notifications.call_event(request.form.to_dict())
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/sms/status', methods=['POST'])
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
@notify.route('/render', methods=['POST'])
def render_notification():
    '''Used for notification emails and receipts
    2 args: 'template' html file and 'data'
    Notification emails: 'data' contains ['account' (not etap format), 'to']
    '''

    try:
        args = request.get_json(force=True)
        logger.debug(args)

        return render_template(
          args['template'],
          to = args['to'],
          account = args['account'],
          event_id=args['event_id']
        )
    except Exception as e:
        logger.error('render: %s ', str(e))
        return 'Error'

#-------------------------------------------------------------------------------
@notify.route('/on_email_status', methods=['GET'])
def on_email_status(args):
    notifications.on_email_status(args)
    return 'OK'
