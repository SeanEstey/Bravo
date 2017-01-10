'''app.notify.views'''

import logging
import twilio.twiml
from bson.objectid import ObjectId
from flask_login import login_required, current_user
from flask import \
    request, jsonify, render_template, redirect, Response, current_app,\
    session, url_for
from .. import utils, cal, parser, get_db
from . import notify
from . import \
    accounts, admin, events, triggers, email, voice, sms, recording, pus, gg,\
    voice_announce
import app.alice.incoming
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@notify.route('/', methods=['GET'])
@login_required
def view_event_list():

    db = get_db()
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

    db = get_db()
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
@notify.route('/new', methods=['POST'])
@login_required
def new_event():
    db = get_db()
    logger.debug(request.form.to_dict())

    agency = db['users'].find_one({'user': current_user.username})['agency']

    template = request.form['template_name']

    try:
        if template == 'green_goods':
            evnt_id = gg.add_event()
        elif template == 'recorded_announcement':
            evnt_id = voice_announce.add_event()
        elif template == 'bpu':
            block = request.form['query_name']

            if parser.is_res(block):
                cal_id = db.agencies.find_one({'name':agency})['cal_ids']['res']
            elif parser.is_bus(block):
                cal_id = db.agencies.find_one({'name':agency})['cal_ids']['bus']
            else:
                return jsonify({'status':'failed', 'description':'Invalid Block name'})

            oauth = db.agencies.find_one({'name':agency})['google']['oauth']

            _date = cal.get_next_block_date(cal_id, block, oauth)

            evnt_id = pus.reminder_event(
                agency,
                block,
                _date
            )
    except Exception as e:
        logger.error(str(e))
        return jsonify({
            'status':'failed',
            'description': str(e)
        })

    event = db.notific_events.find_one({'_id':evnt_id})

    event['triggers'] = events.get_triggers(event['_id'])

    for trigger in event['triggers']:
        # modifying 'triggers' structure for view rendering
        trigger['count'] = triggers.get_count(trigger['_id'])

    return jsonify({
        'status':'success',
        'event': utils.formatter(
            event,
            to_local_time=True,
            bson_to_json=True
        ),
        'view_url': url_for('.view_event', evnt_id=str(event['_id'])),
        'cancel_url': url_for('.cancel_event', evnt_id=str(event['_id'])),
        'description':
            'Reminders for event %s successfully scheduled.' %
            (request.form['query_name'])
    })


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
@notify.route('/<trig_id>/fire', methods=['POST'])
@login_required
def fire_trigger(trig_id):
    if not admin.auth_request_type('admin'):
        return 'Denied'

    db = get_db()
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
@notify.route('/record', methods=['POST'])
@login_required
def record_msg():
    return jsonify(recording.dial())

#-------------------------------------------------------------------------------
@notify.route('/record/answer.xml',methods=['POST'])
def record_xml():
    twiml = recording.on_answer()
    return Response(response=str(twiml), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/record/interact.xml', methods=['POST'])
def record_interact_xml():
    twiml = recording.on_interact()
    return Response(response=str(twiml), mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/record/complete',methods=['POST'])
def record_complete():
    return jsonify(recording.on_complete())

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
    #if alice.is_unsub():
    #    return 'OK'

    # If reply to notific, update any db documents
    sms.on_reply()

    # Have Alice handle response
    a = utils.start_timer()
    response = app.alice.incoming.receive()
    utils.end_timer(a, display=True, lbl='alice request')
    return response

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

#-------------------------------------------------------------------------------
@notify.route('/kill_trigger', methods=['POST'])
@login_required
def kill_trigger():
    return jsonify(triggers.kill())

#-------------------------------------------------------------------------------
@notify.route('/<trig_id>/get_status', methods=['POST'])
@login_required
def get_trig_status(trig_id):
    db = get_db()
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
@notify.route('/<evnt_id>/debug_info', methods=['POST'])
@login_required
def get_debug_info(evnt_id):
    db = get_db()
    event = db.notific_events.find_one({'_id':ObjectId(evnt_id)})

    event['triggers'] = events.get_triggers(event['_id'])

    for trigger in event['triggers']:
        # modifying 'triggers' structure for view rendering
        trigger['count'] = triggers.get_count(trigger['_id'])

    return jsonify(
        utils.formatter(
            event,
            to_local_time=True,
            to_strftime="%m/%-d/%Y @ %-I:%M%p",
            bson_to_json=True
        )
    )
