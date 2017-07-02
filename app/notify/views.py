'''app.notify.views'''
from json import dumps, loads
import twilio.twiml
from bson.objectid import ObjectId as oid
from flask_login import login_required
from flask import g, request, jsonify, render_template, Response, url_for
from app import get_keys
from app.lib.utils import format_bson
from app.main import parser
from . import notify, accounts, events, triggers
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
@notify.route('/', methods=['GET'])
@login_required
def view_event_list():

    """
    user_msg=''
    if request.args.get('status') == 'logged_in':
        user_msg = \
            "Welcome, <b>%s</b>."+\
            "There are <b>%s pending events</b> at the moment."%\
            (g.user.name, events.n_pending())
    """

    return render_template(
        'views/event_list.html',
        title=None,
        #msg=user_msg,
        admin=g.user.is_admin())

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>')
@login_required
def view_event(evnt_id):

    return render_template(
        'views/event.html',
        evnt_id=evnt_id,
        event=format_bson(events.get(oid(evnt_id)), loc_time=True),
        admin=g.user.is_admin(),
        notifications = format_bson(
            events.notifications(oid(evnt_id)),
            loc_time=True,
            dt_str="%m/%-d/%Y"),
        triggers = format_bson(
            events.get_triggers(oid(evnt_id)),
            loc_time=True)
    )

#-------------------------------------------------------------------------------
@notify.route('/<evnt_id>/<acct_id>/skip')
def view_opt_out(evnt_id, acct_id):

    from . import pickups
    valid = pickups.is_valid(evnt_id, acct_id)
    acct = None

    if valid:
        acct = format_bson(
            g.db.accounts.find_one({'_id':oid(acct_id)}),
            loc_time=True, dt_str="%m/%-d/%Y")

    return render_template(
        'views/opt_out.html',
        valid = dumps(valid),
        acct_id = acct_id,
        evnt_id = evnt_id,
        acct = acct
    )
