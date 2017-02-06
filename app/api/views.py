'''app.api.views'''
from . import api
from flask import g
from flask_login import login_required
from app import get_op_stats
from .main import get_var, build_resp, func_call, task_call, WRITE_ME
from app.alice.outgoing import send_welcome
from app.booker.geo import get_maps
from app.booker.search import search
from app.booker.book import make
from app.main import donors
from app.main.signups import lookup_carrier
from app.notify.accounts import edit_fields
from app.notify.events import create_event, cancel_event, reset_event, rmv_notifics
from app.notify.recording import dial_recording
from app.notify.triggers import kill_trigger
from app.routing.main import edit_field

@api.route('/accounts/get', methods=['POST'])
@login_required
def call_accts_get():
    return func_call(donors.get, get_var('acct_id'))

@api.route('accounts/find', methods=['POST'])
@login_required
def call_find_acct():
    # PHP 'check_duplicates'
    return fund_call(WRITE_ME)

@api.route('/accounts/gifts', methods=['POST'])
@login_required
def call_accts_gifts():
    from app.main.tasks import process_entries
    return task_call(process_entries, get_var('entries'))

@api.route('/accounts/receipts', methods=['POST'])
@login_required
def call_accts_receipts():
    from app.main.tasks import send_receipts
    return task_call(send_receipts, get_var('entries'))

@api.route('/accounts/create', methods=['POST'])
@login_required
def call_accts_create():
    return task_call(WRITE_ME, get_var('data'))

@api.route('/agency/update', methods=['POST'])
@login_required
def call_agcy_update():
    return func_call(WRITE_ME, get_var('data'))

@api.route('/alice/welcome', methods=['POST'])
@login_required
def call_alice_welcome():
    return func_call(send_welcome, get_var('acct_id'))

@api.route('/booker/create', methods=['POST'])
@login_required
def call_booker_create():
    return func_call(make)

@api.route('/booker/search', methods=['POST'])
@login_required
def call_booker_search():
    return func_call(search, get_var('query'),
        radius=get_var('radius'), weeks=get_var('weeks'))

@api.route('/booker/maps/get', methods=['POST'])
@login_required
def call_maps_get():
    return func_call(get_maps)

@api.route('/booker/maps/update', methods=['POST'])
@login_required
def call_maps_update():
    from app.booker.tasks import update_maps
    return task_call(update_maps, agcy=g.user.agency)

@api.route('/notify/events/create', methods=['POST'])
@login_required
def call_create_event():
    return func_call(create_event)

@api.route('/notify/events/cancel', methods=['POST'])
@login_required
def call_cancel_event():
    return func_call(cancel_event, evnt_id=get_var('evnt_id'))

@api.route('/notify/events/reset', methods=['POST'])
@login_required
def call_reset_event():
    return func_call(reset_event, get_var('evnt_id'))

@api.route('/notify/events/record', methods=['POST'])
@login_required
def call_record():
    return func_call(dial_recording)

@api.route('/notify/accts/edit', methods=['POST'])
@login_required
def call_notify_acct_edit():
    return func_call(edit_fields, get_var('acct_id'), get_var('fields'))

@api.route('/notify/accts/remove', methods=['POST'])
@login_required
def call_notify_acct_rmv():
    return func_call(rmv_notifics, get_var('evnt_id'), get_var('acct_id'))

@api.route('/notify/triggers/fire', methods=['POST'])
@login_required
def call_trigger_fire():
    from app.notify.tasks import fire_trigger
    return task_call(fire_trigger, get_var('trig_id'))

@api.route('/notify/triggers/kill', methods=['POST'])
@login_required
def call_trigger_kill():
    return func_call(kill_trigger, get_var('trig_id'))

@api.route('/notify/acct/skip', methods=['POST'])
@login_required
def call_skip_pickup():
    return task_call(kill_trigger)

@api.route('/phone/lookup', methods=['POST'])
@login_required
def call_phone_lookup():
    return func_call(lookup_carrier, get_var('phone'))

@api.route('/query/block_size', methods=['POST'])
@login_required
def call_block_size():
    return func_call(WRITE_ME)

@api.route('/query/route_size', methods=['POST'])
@login_required
def call_route_size():
    return task_call(WRITE_ME)

@api.route('/routing/build', methods=['POST'])
@login_required
def call_route_build():
    from app.routing.tasks import build_route
    return task_call(build_route, get_var('route_id'), job_id=get_var('job_id'))

@api.route('/routing/edit', methods=['POST'])
@login_required
def call_route_edit():
    return func_call(edit_field, get_var('route_id'), get_var('field'), get_var('value'))

@api.route('/server/properties', methods=['POST'])
@login_required
def call_op_stats():
    return func_call(get_op_stats)
