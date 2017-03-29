'''app.api.views'''
import logging
from dateutil.parser import parse
from json import loads
from flask import g, request
from flask_login import login_required
from app import get_logger, get_server_prop
from app.main.etap import block_size, route_size
from app.alice.outgoing import send_welcome, compose
from app.booker.geo import get_maps
from app.booker.search import search
from app.booker.book import make
from app.main import donors
from app.main.receipts import preview
from app.main.signups import lookup_carrier
from app.notify.accounts import edit_fields
from app.notify.events import create_event, cancel_event, dump_event, reset_event, rmv_notifics
from app.notify.recording import dial_recording
from app.notify.triggers import kill_trigger
from app.notify.voice import get_token
from app.routing.main import edit_field
from . import api
from .manager import get_var, build_resp, func_call, task_call, WRITE_ME

@api.route('/accounts/submit_form', methods=['POST'])
def accts_add_form():
    # TODO: add auth requirement
    from app.main.tasks import add_form_signup
    return task_call(add_form_signup, data=request.form.to_dict())

@api.route('/accounts/get_pickup', methods=['POST'])
def accts_get_pickup():
    # TODO: add auth requirement
    return func_call(donors.get_next_pickup, get_var('email'), agcy=get_var('agcy'))

@api.route('/accounts/estimate_trend', methods=['POST'])
@login_required
def estmt_trend():
    from app.main.tasks import estimate_trend
    return task_call(
        estimate_trend,
        get_var('date'),
        loads(get_var('donations')),
        get_var('ss_id'),
        get_var('ss_row'))

@api.route('/accounts/get_donations', methods=['POST'])
@login_required
def get_donations():
    return func_call(
        donors.get_donations,
        get_var('acct_id'),
        parse(get_var('start_d')).date(),
        parse(get_var('end_d')).date())

@api.route('/accounts/save_rfu', methods=['POST'])
@login_required
def accts_save_rfu():
    # TODO: add auth requirement
    return func_call(donors.save_rfu,
        get_var('acct_id'), get_var('body'), get_var('date'),
        get_var('ref'), get_var('fields')) #, agcy=get_var('agcy'))

@api.route('/accounts/create', methods=['POST'])
@login_required
def call_accts_create():
    from app.main.tasks import create_accounts
    return task_call(create_accounts, get_var('accts'), agcy=get_var('agcy'))

@api.route('accounts/find', methods=['POST'])
@login_required
def call_find_acct():
    # PHP 'check_duplicates'
    return func_call(WRITE_ME)

@api.route('/accounts/get', methods=['POST'])
@login_required
def call_accts_get():
    return func_call(donors.get, get_var('acct_id'))

@api.route('/accounts/gifts', methods=['POST'])
@login_required
def call_accts_gifts():
    from app.main.tasks import process_entries
    return task_call(process_entries, get_var('entries'), agcy=get_var('agcy'))

@api.route('/accounts/receipts', methods=['POST'])
@login_required
def call_accts_receipts():
    from app.main.tasks import send_receipts
    return task_call(send_receipts, get_var('entries'))

@api.route('/accounts/preview_receipt', methods=['POST'])
@login_required
def call_acct_preview_receipt():
    return func_call(preview, get_var('acct_id'), get_var('type_'))

@api.route('/agency/update', methods=['POST'])
@login_required
def call_agcy_update():
    #admin.update_agency_conf()
    return func_call(WRITE_ME, get_var('data'))

@api.route('/alice/welcome', methods=['POST'])
@login_required
def alice_send_welcome():
    return func_call(send_welcome, get_var('acct_id'))

@api.route('/alice/compose', methods=['POST'])
@login_required
def alice_send_msg():
    return func_call(compose, g.user.agency, get_var('body'), get_var('to'), find_session=True)

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

@api.route('/notify/events/preview/token', methods=['POST'])
@login_required
def call_preview_token():
    return func_call(get_token)

@api.route('/notify/events/dump', methods=['POST'])
@login_required
def call_dump_event():
    return func_call(dump_event, evnt_id=get_var('evnt_id'))

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
    return func_call(edit_fields, str(get_var('acct_id')), loads(get_var('fields')))

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
    return func_call(block_size, get_var('category'), get_var('query'))

@api.route('/query/route_size', methods=['POST'])
@login_required
def call_route_size():
    return func_call(route_size, get_var('category'), get_var('query'), get_var('date'))

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
    return func_call(get_server_prop)
