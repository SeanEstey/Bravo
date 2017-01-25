'''app.notify.views'''
import logging
import twilio.twiml
from bson.objectid import ObjectId
from flask_login import login_required
from flask import g, request, jsonify, render_template, Response, url_for
from app import smart_emit, get_keys, utils, cal, parser
from .tasks import fire_trigger, skip_pickup
from . import notify, accounts, admin, events, triggers, email, voice, sms,\
    recording, pickups, gg, voice_announce

log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@notify.route('/', methods=['GET'])
@login_required
def view_event_list():
    event_list = events.get_list(g.user.agency)

    smart_emit('test', 'notify/views smart_emit')

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
      admin=g.user.is_admin()
    )

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>')
@login_required
def view_event(evnt_id):
    '''GUI event view'''
    from flask import current_app

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
        admin=g.user.is_admin()
    )

#-------------------------------------------------------------------------------
@notify.route('/new', methods=['POST'])
@login_required
def new_event():
    log.debug(request.form)

    template = request.form['template_name']

    try:
        if template == 'green_goods':
            evnt_id = gg.add_event()
        elif template == 'recorded_announcement':
            evnt_id = voice_announce.add_event()
        elif template == 'bpu':
            block = request.form['query_name']

            if parser.is_res(block):
                cal_id = get_keys('cal_ids')['res']
            elif parser.is_bus(block):
                cal_id = get_keys('cal_ids')['bus']
            else:
                return jsonify({'status':'failed', 'description':'Invalid Block name'})

            _date = cal.get_next_block_date(
                cal_id, block, get_keys('google')['oauth'])

            evnt_id = pickups.create_reminder(
                g.user.agency,
                block,
                _date
            )
    except Exception as e:
        log.error(str(e))
        log.debug('', exc_info=True)
        return jsonify({
            'status':'failed',
            'description': str(e)
        })

    event = g.db.notific_events.find_one({'_id':evnt_id})

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
def _fire_trigger(trig_id):
    if not admin.auth_request_type('admin'):
        return 'Denied'

    trigger = g.db.triggers.find_one({'_id':ObjectId(trig_id)})

    fire_trigger.delay(args=[str(trigger['evnt_id']), trig_id],kwargs={})

    return jsonify({'status':'OK'})

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/<acct_id>/no_pickup', methods=['GET'])
def no_pickup(evnt_id, acct_id):

    if not pickups.is_valid(evnt_id, acct_id):
        logger.error(
            'notific event or acct not found (evnt_id=%s, acct_id=%s)',
            evnt_id, acct_id)
        return 'Sorry there was an error fulfilling your request'

    skip_pickup.delay(args=[evnt_id, acct_id],kwargs={})

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
    log.debug(r)
    return Response(r, mimetype='text/xml')

#-------------------------------------------------------------------------------
@notify.route('/voice/play/interact.xml', methods=['POST'])
def get_call_interact_xml():
    r = str(voice.on_interact())
    log.debug(r)
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
@notify.route('/call/nis', methods=['POST'])
def nis():
    log.info('NIS!')
    record = request.get_json()

    rfu.delay(
        args=[
            g.user.agency,
            record['custom']['to'] + ' not in service'],
        kwargs={
            'a_id': record['account_id'],
            'block': record['custom']['block']})
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
    status = g.db.triggers.find_one({'_id':ObjectId(trig_id)})['status']
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
    event = g.db.notific_events.find_one({'_id':ObjectId(evnt_id)})
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
