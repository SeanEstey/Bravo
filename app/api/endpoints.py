'''app.api.endpoints'''
import logging
from json import loads
from flask import g, request, Response
from flask_login import login_required
from app.main import donors
from app.notify.events import create_event, cancel_event, dump_event, reset_event, rmv_notifics
from . import api
from app.api.manager import var, build_resp, func_call, task_call
log = logging.getLogger(__name__)

@api.route('/accounts/submit_form', methods=['POST'])
#@login_required
def _submit_form_signup():
    from app.main.tasks import add_form_signup
    return task_call(add_form_signup, data=request.form.to_dict())

@api.route('/accounts/get_pickup', methods=['POST'])
#@login_required
def _get_next_pickup():
    g.group = var('agcy')
    return func_call(donors.get_next_pickup, var('email'))

@api.route('/db/backup', methods=['GET', 'POST'])
@login_required
def _backup_db():
    from app.main.tasks import backup_mongo
    return task_call(backup_mongo)

@api.route('/cache/gifts', methods=['GET', 'POST'])
@login_required
def _api_cache_gifts():
    from app.main.tasks import cache_gifts
    return task_call(cache_gifts)

@api.route('/accounts/estimate_trend', methods=['POST'])
@login_required
def _est_trend():
    from app.main.tasks import estimate_trend
    return task_call(
        estimate_trend,
        var('date'),
        loads(var('donations')),
        var('ss_id'),
        var('ss_row'))

@api.route('/accounts/get_donations', methods=['POST'])
@login_required
def _get_donations():
    from dateutil.parser import parse
    return func_call(
        donors.get_donations,
        var('acct_id'),
        parse(var('start_d')).date(),
        parse(var('end_d')).date())

@api.route('/accounts/save_rfu', methods=['POST'])
@login_required
def _save_rfu():
    return func_call(
        donors.save_rfu,
        var('acct_id'), var('body'), var('date'), var('ref'), var('fields'))

@api.route('/accounts/create', methods=['POST'])
@login_required
def _create_accts():
    from app.main.tasks import create_accounts
    return task_call(create_accounts, var('accts'), agcy=var('agcy'))

@api.route('/accounts/find', methods=['POST'])
@login_required
def _find_acct():
    from app.main.signups import check_duplicates
    return func_call(check_duplicates,
        name=var("name"),
        email=var("email"),
        address=var("address"),
        phone=var("phone"))

@api.route('/accounts/get', methods=['POST'])
@login_required
def _get_accts():
    return func_call(donors.get, var('acct_id'))

@api.route('/accounts/gifts', methods=['POST'])
@login_required
def _do_gifts():
    from app.main.tasks import process_entries
    return task_call(
        process_entries,
        loads(var('entries')),
        wks=var('wks'),
        col=var('col'))

@api.route('/accounts/receipts', methods=['POST'])
@login_required
def _do_receipts():
    from app.main.tasks import send_receipts
    return task_call(send_receipts, var('entries'))

@api.route('/account/update', methods=['POST'])
@login_required
def _update_acct():
    from app.main.etap import call
    return func_call(call, 'modify_acct', var('acct_id'), var('udf'), var('persona'))

@api.route('/accounts/update', methods=['POST'])
@login_required
def _update_accts():
    from app.main.tasks import process_entries
    return task_call(
        process_entries,
        loads(var('accts')),
        wks=var('wks'),
        col=var('col'))

@api.route('/accounts/preview_receipt', methods=['POST'])
@login_required
def _preview_receipt():
    from app.main.receipts import preview
    return func_call(preview, var('acct_id'), var('type_'))

@api.route('/accounts/find_within_map', methods=['POST'])
@login_required
def _find_zone_accts():
    from app.main.tasks import find_zone_accounts
    return task_call(find_zone_accounts,
        zone=var('map_title'), blocks=loads(var('blocks')))

@api.route('/agency/conf/get', methods=['POST'])
@login_required
def _get_group_conf():
    from app.main import agency
    return func_call(agency.get_conf)

@api.route('/agency/conf/update', methods=['POST'])
@login_required
def _update_group_conf():
    from app.main import agency
    return func_call(agency.update_conf, var('data'))

@api.route('/agency/properties/get', methods=['POST'])
@login_required
def _get_admin_prop():
    from app.main.agency import get_admin_prop
    return func_call(get_admin_prop)

@api.route('/alice/welcome', methods=['POST'])
@login_required
def _send_welcome():
    from app.alice.outgoing import send_welcome
    return func_call(send_welcome, var('acct_id'))

@api.route('/alice/compose', methods=['POST'])
@login_required
def _compose():
    from app.alice.outgoing import compose
    return func_call(
        compose,
        var('body'), var('to'),
        find_session=True)

@api.route('/alice/chatlogs', methods=['POST'])
@login_required
def _get_chatlogs():
    from app.alice.util import get_chatlogs
    return func_call(get_chatlogs, serialize=True)

@api.route('/booker/create', methods=['POST'])
@login_required
def _book_acct():
    from app.booker.book import make
    return func_call(make)

@api.route('/booker/get_acct_geo', methods=['POST'])
@login_required
def _get_acct_geo():
    from app.booker.search import get_acct_geo
    return func_call(
        get_acct_geo,
        var('acct_id'))

@api.route('/booker/search', methods=['POST'])
@login_required
def _search_bookings():
    from app.booker.search import search
    return func_call(
        search, var('query'),
        radius=var('radius'),
        weeks=var('weeks'))

@api.route('/booker/maps/get', methods=['POST'])
@login_required
def _get_booker_maps():
    from app.booker.geo import get_maps
    return func_call(get_maps)

@api.route('/maps/get', methods=['POST'])
@login_required
def _get_maps():
    from app.main.maps import get_maps
    return func_call(get_maps)

@api.route('/maps/update', methods=['POST'])
@login_required
def _update_maps():
    from app.booker.tasks import update_maps
    return task_call(update_maps, agcy=g.group)

@api.route('/booker/maps/update', methods=['POST'])
@login_required
def _update_booker_maps():
    from app.booker.tasks import update_maps
    return task_call(update_maps, agcy=g.user.agency)

@api.route('/leaderboard/get', methods=['POST'])
@login_required
def _get_leaderboards():
    from app.main.leaderboard import get_all_rankings
    return func_call(get_all_rankings)

@api.route('/notify/events/get_recent', methods=['POST'])
@login_required
def get_recent_events():
    from app.notify.events import get_recent
    return func_call(get_recent)

@api.route('/notify/events/create', methods=['POST'])
@login_required
def _create_event():
    return func_call(create_event)

@api.route('/notify/events/cancel', methods=['POST'])
@login_required
def _cancel_event():
    return func_call(cancel_event, evnt_id=var('evnt_id'))

@api.route('/notify/events/preview/token', methods=['POST'])
@login_required
def _preview_token():
    from app.notify.voice import get_token
    return func_call(get_token)

@api.route('/notify/events/dump', methods=['POST'])
@login_required
def _dump_event():
    return func_call(dump_event, evnt_id=var('evnt_id'))

@api.route('/notify/events/reset', methods=['POST'])
@login_required
def _reset_event():
    return func_call(reset_event, var('evnt_id'))

@api.route('/notify/events/record', methods=['POST'])
@login_required
def _record_voice():
    from app.notify.recording import dial_recording
    return func_call(dial_recording)

@api.route('/notify/accts/edit', methods=['POST'])
@login_required
def _edit_acct_fields():
    from app.notify.accounts import edit_fields
    return func_call(edit_fields, str(var('acct_id')), loads(var('fields')))

@api.route('/notify/accts/remove', methods=['POST'])
@login_required
def _rmv_notific():
    return func_call(rmv_notifics, var('evnt_id'), var('acct_id'))

@api.route('/notify/accts/optout', methods=['POST'])
def _optout_pickup():
    from app.notify.pickups import is_valid
    from app.notify.tasks import skip_pickup

    evnt_id = var('evnt_id')
    acct_id = var('acct_id')

    if not is_valid(evnt_id, acct_id):
        from json import dumps
        return Response(
            response=dumps({
                'status':'failed',
                'desc':'Invalid account/event or already opted out.'
            }),
            status=200,
            mimetype='application/json')

    return task_call(skip_pickup, evnt_id=evnt_id, acct_id=acct_id)

@api.route('/notify/triggers/fire', methods=['POST'])
@login_required
def _fire_trig():
    from app.notify.tasks import fire_trigger
    return task_call(fire_trigger, var('trig_id'))

@api.route('/notify/triggers/kill', methods=['POST'])
@login_required
def _kill_trig():
    from app.notify.triggers import kill_trigger
    return func_call(kill_trigger, var('trig_id'))

@api.route('/notify/preview/sms', methods=['POST'])
@login_required
def _sms_preview():
    from app.notify.sms import preview
    return func_call(preview)

@api.route('/notify/preview/email', methods=['POST'])
@login_required
def _email_preview():
    from app.notify.email import preview
    return func_call(preview, var('template'), var('state'))

@api.route('/phone/lookup', methods=['POST'])
@login_required
def _carrier_lookup():
    return func_call(lookup_carrier, var('phone'))

@api.route('/query/get', methods=['GET','POST'])
@login_required
def _get_query():
    from app.main.etap import get_query
    return func_call(get_query, var('name'), category=var('category'))

@api.route('/query/block_size', methods=['POST'])
@login_required
def _block_size():
    from app.main.etap import block_size
    return func_call(block_size, var('category'), var('query'))

@api.route('/query/route_size', methods=['POST'])
@login_required
def _route_size():
    from app.main.etap import route_size
    return func_call(route_size, var('category'), var('query'), var('date'))

@api.route('/routing/build', methods=['POST'])
@login_required
def _build_route():
    from app.routing.tasks import build_route
    return task_call(build_route, var('route_id'), job_id=var('job_id'))

@api.route('/routing/edit', methods=['POST'])
@login_required
def _edit_route():
    from app.routing.main import edit_field
    return func_call(edit_field, var('route_id'), var('field'), var('value'))

@api.route('/server/properties', methods=['POST'])
@login_required
def _server_prop():
    from app import get_server_prop
    return func_call(get_server_prop)

@api.route('/signups/welcome/send', methods=['POST'])
@login_required
def _signup_welcome():
    from app.main.signups import send_welcome
    return func_call(send_welcome)

@api.route('/logger/write', methods=['POST'])
@login_required
def _write_log():
    lvl = var('level').upper()

    if lvl == 'INFO':
        return func_call(log.info, var('msg'))
    elif lvl == 'WARNING':
        return func_call(log.warning, var('msg'))
    elif lvl == 'ERROR':
        return func_call(log.error, var('msg'))
    else:
        raise Exception('invalid level var')

@api.route('/logger/get', methods=['POST'])
@login_required
def _get_logs():
    from app.main.logs import get_logs
    return func_call(get_logs)

@api.route('/user/login', methods=['POST'])
def _login_user():
    from app.auth.manager import login
    return func_call(login, var('username'), var('password'))

@api.route('/user/logout', methods=['POST'])
@login_required
def _logout_user():
    from app.auth.manager import logout
    return func_call(logout)

@api.route('/user/get', methods=['POST'])
@login_required
def _get_user_info():
    return func_call(g.user.to_dict)
