'''app.notify.views'''
from json import dumps
import twilio.twiml
from bson.objectid import ObjectId
from flask_login import login_required
from flask import g, request, jsonify, render_template, Response, url_for
from app import smart_emit, get_keys
from app.lib.utils import formatter, to_title_case
from app.main import parser
from . import notify, accounts, events, triggers
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
@notify.route('/', methods=['GET'])
@login_required
def view_event_list():

    event_list = events.get_list(g.user.agency)

    for event in event_list:
        # modifying 'notification_event' structure for view rendering
        event['triggers'] = events.get_triggers(event['_id'])

        for trigger in event['triggers']:
            # modifying 'triggers' structure for view rendering
            trigger['count'] = triggers.get_count(trigger['_id'])

    msg = ""

    if request.args.get('status') == 'logged_in':
        n_pending = g.db.events.find(
            {'agency':g.user.agency, 'status':'pending'}
        ).count()

        msg = "Welcome, <b>%s</b>. There are <b>%s pending events</b> at the moment." %(
            g.user.name, n_pending)

    return render_template(
      'views/event_list.html',
      title=None,
      events=event_list,
      msg=msg,
      admin=g.user.is_admin())

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>')
@login_required
def view_event(evnt_id):

    event = events.get(ObjectId(evnt_id))
    notific_list = list(events.get_notifics(ObjectId(evnt_id)))
    trigger_list = events.get_triggers(ObjectId(evnt_id))

    notific_list = formatter(
        notific_list,
        to_local_time=True,
        to_strftime="%m/%-d/%Y",
        bson_to_json=True)

    for trigger in trigger_list:
        trigger['type'] = to_title_case(trigger['type'])

    return render_template(
        'views/event.html',
        notific_list=notific_list,
        evnt_id=evnt_id,
        event=event,
        triggers=trigger_list,
        admin=g.user.is_admin())

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/<acct_id>/skip')
def view_opt_out(evnt_id, acct_id):

    from . import pickups
    valid = pickups.is_valid(evnt_id, acct_id)
    acct = None

    if valid:
        acct = formatter(
            g.db.accounts.find_one({'_id':ObjectId(acct_id)}),
            to_local_time=True,
            to_strftime="%m/%-d/%Y",
            bson_to_json=True)

    return render_template(
        'views/opt_out.html',
        valid = dumps(valid),
        acct_id = acct_id,
        evnt_id = evnt_id,
        acct = acct
    )
