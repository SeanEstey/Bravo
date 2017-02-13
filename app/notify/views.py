'''app.notify.views'''
import logging
import twilio.twiml
from bson.objectid import ObjectId
from flask_login import login_required
from flask import g, request, jsonify, render_template, Response, url_for
from app import get_logger, smart_emit, get_keys, utils, cal, parser
from . import notify, accounts, events, triggers
log = get_logger(__name__)

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
      admin=g.user.is_admin())

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
        bson_to_json=True)

    for trigger in trigger_list:
        trigger['type'] = utils.to_title_case(trigger['type'])

    return render_template(
        'views/event.html',
        title=current_app.config['TITLE'],
        notific_list=notific_list,
        evnt_id=evnt_id,
        event=event,
        triggers=trigger_list,
        admin=g.user.is_admin())

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
@notify.route('/<trig_id>/get_status', methods=['POST'])
@login_required
def get_trig_status(trig_id):
    status = g.db.triggers.find_one({'_id':ObjectId(trig_id)})['status']
    return jsonify({'status':status, 'trig_id':trig_id})

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
            bson_to_json=True))
