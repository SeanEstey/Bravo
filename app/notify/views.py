'''notify.views'''

import json
import twilio.twiml
import os
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
from . import accounts, admin, events, triggers, email, voice, sms, \
              recording, pickup_service
from .. import utils, schedule, parser
from app.main import sms_assistant
from .. import db
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@notify.route('/kill_trigger', methods=['POST'])
@login_required
def kill_trigger():
    return jsonify(triggers.kill())

#-------------------------------------------------------------------------------
@notify.route('/<trig_id>/get_status', methods=['POST'])
@login_required
def get_trig_status(trig_id):
    status = db.triggers.find_one({'_id':ObjectId(trig_id)})['status']
    return jsonify({'status':status, 'trig_id':trig_id})

#-------------------------------------------------------------------------------
@notify.route('/get_op_stats', methods=['POST'])
@login_required
def get_op_stats():
    stats = admin.get_op_stats()
    if not stats:
        return jsonify({'status':'failed'})

    return jsonify(stats)

#-------------------------------------------------------------------------------
@notify.route('/', methods=['GET'])
@login_required
def view_event_list():

    user = db['users'].find_one({'user': current_user.username})
    agency = user['agency']

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
      events=event_list,
      admin=user['admin']
    )

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>')
@login_required
def view_event(evnt_id):
    '''GUI event view'''

    admin = db['users'].find_one({'user': current_user.username})['admin']
    event = events.get(ObjectId(evnt_id))
    notific_list = list(events.get_notifics(ObjectId(evnt_id)))
    trigger_list = events.get_triggers(ObjectId(evnt_id))

    notific_list = utils.formatter(
        notific_list,
        to_local_time=True,
        to_strftime="%m/%-d/%Y",
        bson_to_json=True
    )

    for trigger in trigger_list:
        trigger['type'] = utils.to_title_case(trigger['type']);

    return render_template(
        'views/event.html',
        title=current_app.config['TITLE'],
        notific_list=notific_list,
        evnt_id=evnt_id,
        event=event,
        triggers=trigger_list,
        admin=admin
    )

#-------------------------------------------------------------------------------
@notify.route('/new')
@login_required
def new_event():
    agency = db['users'].find_one({'user': current_user.username})['agency']

    conf= db['agencies'].find_one({'name':agency})
    try:
        foo = 1
        #with open('app/templates/schemas/'+agency+'.json') as json_file:
        #  templates = json.load(json_file)['reminders']
    except Exception as e:
        logger.error("Couldn't open json schemas file")
        return "Error"

    return render_template('views/new_event.html',
        templates=None,
        etap_query_folder=conf['etapestry']['schedule_events_folder'],
        title=current_app.config['TITLE'])

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
    if not events.remove(ObjectId(evnt_id)):
        return jsonify({'status': 'failed'})

    return jsonify({'status': 'success'})

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
    if not events.rmv_notifics(ObjectId(evnt_id), ObjectId(acct_id)):
        return jsonify({'status':'failed'})

    return jsonify({'status':'success'})

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/dup_acct', methods=['GET'])
@login_required
def dup_acct(evnt_id):
    if events.dup_random_acct(ObjectId(evnt_id)):
        return 'OK'
    else:
        return 'Error'

#-------------------------------------------------------------------------------
@notify.route('/<acct_id>/edit', methods=['POST'])
@login_required
def edit_msg(acct_id):
    return accounts.edit(ObjectId(acct_id), request.form.items())



#-------------------------------------------------------------------------------
@notify.route('/<block>/schedule', methods=['POST'])
@login_required
def schedule_block(block):
    if not admin.auth_request_type('admin'):
        return 'Denied'

    agency = db['users'].find_one({'user': current_user.username})['agency']

    if parser.is_res(block):
        cal_id = db.agencies.find_one({'name':agency})['cal_ids']['res']
    elif parser.is_bus(block):
        cal_id = db.agencies.find_one({'name':agency})['cal_ids']['bus']

    oauth = db.agencies.find_one({'name':agency})['google']['oauth']

    _date = schedule.get_next_block_date(cal_id, block, oauth)

    logger.info('loading reminders for %s on %s', block, _date)

    pickup_service.create_reminder_event(agency, block, _date)

    return jsonify({
        'status':'OK',
        'description': 'reminder event successfully scheduled for Block %s on %s' %
        (block, _date)
    })


#-------------------------------------------------------------------------------
@notify.route('/<trig_id>/fire', methods=['POST'])
@login_required
def fire_trigger(trig_id):
    if not admin.auth_request_type('admin'):
        return 'Denied'

    trigger = db['triggers'].find_one({'_id':ObjectId(trig_id)})

    from .. import tasks
    tasks.fire_trigger.apply_async(
        args=[str(trigger['evnt_id']), trig_id],
        queue=current_app.config['DB'])

    return jsonify({'status':'OK'})

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
    r = str(voice.on_answer())
    logger.debug(r)
    return Response(r, mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/play/interact.xml', methods=['POST'])
def get_call_interact_xml():
    r = str(voice.on_interact())
    logger.debug(r)
    return Response(r, mimetype='text/xml')

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
    '''Shared endpoint for incoming SMS. Set by Twilio SMS application
    '''
    if sms_assistant.is_unsub():
        return 'OK'

    if sms.is_reply():
        return sms.on_reply()
    else:
        return jsonify({'response':sms_assistant.on_receive()})

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
