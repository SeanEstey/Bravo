'''notify.views'''

import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import request, jsonify, render_template, \
    redirect, Response, current_app
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import logging
import bson.json_util
from flask_socketio import SocketIO, emit

from . import notify
from . import events, triggers, email, voice, sms, recording#, pickup_service
from .. import utils
from .. import db
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@notify.route('/', methods=['GET'])
@login_required
def view_event_list():

    agency = db['users'].find_one({'user': current_user.username})['agency']

    event_list = events.get_list(agency)

    for event in event_list:
        # modifying 'notification_event' structure for view rendering
        event['triggers'] = events.get_triggers(event['_id'])

        for trigger in event['triggers']:
            # modifying 'triggers' structure for view rendering
            trigger['count'] = triggers.get_count(trigger['_id'])

    return render_template(
      'views/event_list.html',
      title=None,
      events=event_list
    )

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>')
@login_required
def view_event(evnt_id):
    '''GUI event view'''

    event = events.get(ObjectId(evnt_id))
    notific_list = list(events.get_notifics(ObjectId(evnt_id)))
    trigger_list = events.get_triggers(ObjectId(evnt_id))

    notific_list = utils.formatter(
        notific_list,
        to_local_time=True,
        to_strftime="%m/%-d/%Y",
        bson_to_json=True
    )

    return render_template(
        'views/event.html',
        title=current_app.config['TITLE'],
        notific_list=notific_list,
        evnt_id=evnt_id,
        event=event,
        triggers=trigger_list
        #template=job['schema']['import_fields']
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

    return render_template('views/new_event.html', templates=templates, title=current_app.config['TITLE'])

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
@notify.route('/<evnt_id>/cancel')
@login_required
def cancel_event(evnt_id):
    events.remove(ObjectId(evnt_id))
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/reset')
@login_required
def reset_event(evnt_id):
    events.reset(evnt_id)
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/complete')
@login_required
def job_complete(evnt_id):
    '''Email job summary, update job status'''

    logger.info('Job [ID %s] complete!', evnt_id)

    # TODO: Send socket to web app to display completed status
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/<acct_id>/remove', methods=['POST'])
@login_required
def rmv_notifics(evnt_id, acct_id):
    n = events.rmv_notifics(ObjectId(evnt_id), ObjectId(acct_id))
    return str(n)

#-------------------------------------------------------------------------------
@notify.route('/<acct_id>/edit', methods=['POST'])
@login_required
def edit_msg(acct_id):
    accounts.edit(ObjectId(acct_id), request.form.items())
    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<trig_id>/fire', methods=['POST'])
@login_required
def fire_trigger(trig_id):
    from .. import tasks

    trigger = db['triggers'].find_one({'_id':ObjectId(trig_id)})

    tasks.fire_trigger.apply_async(
        args=[str(trigger['evnt_id']), trig_id],
        queue=current_app.config['DB'])

    return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/<acct_id>/no_pickup', methods=['GET'])
def no_pickup(evnt_id, acct_id):
    '''Script run via reminder email'''

    from .. import tasks

    tasks.cancel_pickup.apply_async(
        args=[evnt_id, acct_id],
        queue=current_app.config['DB'])

    return 'Thank You'

#-------------------------------------------------------------------------------
@notify.route('/play/sample', methods=['POST'])
def play_sample_rem():
    twiml = twilio.twiml.Response()
    twiml.say("test")
    return Response(response=str(twiml), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/get/token', methods=['GET'])
def get_twilio_token():
    token = recording.get_twilio_token()
    return jsonify(identity="sean", token=token)

#-------------------------------------------------------------------------------
@notify.route('/voice/record/request', methods=['POST'])
def record_msg():
    call = recording.dial(request.values.to_dict())
    return Response(response=json.dumps({'status':call.status}), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/record/answer.xml',methods=['POST'])
def record_xml():
    twiml = recording.on_answer(request.values.to_dict())
    return Response(response=str(twiml), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/record/complete.xml', methods=['POST'])
def record_complete_xml():
    twiml = recording.on_complete(request.values.to_dict())
    return Response(response=str(twiml), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/play/answer.xml',methods=['POST'])
def get_call_answer_xml():
    return Response(str(voice.on_answer()), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/play/interact.xml', methods=['POST'])
def get_call_interact_xml():
    return Response(str(voice.on_interact()), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/complete', methods=['POST'])
def call_complete():
    return voice.on_complete()

#-------------------------------------------------------------------------------
@notify.route('/voice/fallback', methods=['POST'])
def call_fallback():
    return voice.on_error()

#-------------------------------------------------------------------------------
@notify.route('/sms/status', methods=['POST'])
def sms_status():
    return sms.on_status()

#-------------------------------------------------------------------------------
@notify.route('/sms/receive', methods=['POST'])
def sms_received():
    '''Shared endpoint for incoming SMS. Route to appropriate handlers.
    '''

    status = sms.on_reply()

    if status:
        return str(status)
    else:
        # BPU Pickup Date Request
        # TODO: add code
        return 'OK'

#-------------------------------------------------------------------------------
@notify.route('/call/nis', methods=['POST'])
def nis():
    logger.info('NIS!')

    record = request.get_json()

    #agency = db['agencies'].

    try:
        from .. import tasks
        #tasks.rfu.apply_async(
        #    args=[
        #      record['custom']['to'] + ' not in service',
        #      a_id=record['account_id'],
        #      block=record['custom']['block']
        #    )
    except Exception, e:
        logger.info('%s /call/nis' % request.values.items(), exc_info=True)
    return str(e)
