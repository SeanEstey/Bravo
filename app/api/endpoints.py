"""app.api.endpoints

API interface. Paths with @login_required must be called either from logged-in
client or provide API key in request headers. Paths without @login_required can
be called anonymously.
"""

import json, logging
from json import loads
from flask import g,request,Response
from flask_login import login_required
from app.lib.timer import Timer
from . import api
from app.api.manager import var,func_call,task_call

log = logging.getLogger('api.endpoints')

@api.before_request
def _api_setup():
    g.tag = 'api'
    g.timer = Timer()

##### API CALLS #####

@api.route('/accounts/submit_form', methods=['POST'])
def _submit_form_signup():
    # TODO: Update URL to /signups/submit on emptiestowinn.com
    from app.main.tasks import add_form_signup
    return task_call(add_form_signup, data=request.form.to_dict())

@api.route('/accounts/get_pickup', methods=['POST'])
def _get_next_pickup():
    from app.main.donors import get_next_pickup
    g.group = var('agcy')
    return func_call(get_next_pickup, var('email'))

@api.route('/accounts/gift_history', methods=['GET','POST'])
@login_required
def _get_sum_stats():
    from app.main.donors import gift_history
    return func_call(gift_history, var('ref'))

@api.route('/accounts/estimate_trend', methods=['POST'])
@login_required
def _trend():
    from app.main.tasks import estimate_trend
    return task_call(estimate_trend, var('date'), loads(var('donations')), var('ss_id'), var('ss_row'))

@api.route('/accounts/save_rfu', methods=['POST'])
@login_required
def _save_rfu():
    from app.main.donors import save_rfu
    return func_call(save_rfu, var('acct_id'), var('body'), var('date'), var('ref'), var('fields'))

@api.route('/accounts/create', methods=['POST'])
@login_required
def _create_accts():
    from app.main.tasks import create_accounts
    return task_call(create_accounts, var('accts'), group=var('agcy'))

@api.route('/accounts/find', methods=['POST'])
@login_required
def _find_acct():
    from app.main.signups import check_duplicates
    return func_call(check_duplicates, name=var("name"), email=var("email"), address=var("address"), phone=var("phone"))

@api.route('/accounts/get', methods=['POST'])
@login_required
def _get_accts():
    from app.main import donors
    return func_call(donors.get, var('acct_id'), cached=var('cached'))

@api.route('/accounts/get/autocomplete', methods=['POST'])
@login_required
def _get_autocomplete():
    from app.main.donors import get_matches
    return func_call(get_matches, var('query'))

@api.route('/accounts/get/location', methods=['POST'])
@login_required
def _get_location():
    from app.main.donors import get_location
    return func_call(get_location, var('acct_id'))

@api.route('/accounts/gifts', methods=['POST'])
@login_required
def _do_gifts():
    from app.main.tasks import process_entries
    return task_call(process_entries, loads(var('entries')), wks=var('wks'), col=var('col'))

@api.route('/accounts/receipts', methods=['POST'])
@login_required
def _do_receipts():
    from app.main.tasks import send_receipts
    return task_call(send_receipts, var('entries'))

@api.route('/accounts/update', methods=['POST'])
@login_required
def _update_acct():
    from app.main.etapestry import mod_acct

    acct_id = var('acct_id')
    persona = loads(var('persona')) if var('persona') else {}
    udf = loads(var('udf')) if var('udf') else {}
    log.debug('acct_id=%s, udf=%s, persona=%s', acct_id, udf, persona)
    return func_call(mod_acct, acct_id, udf=udf, persona=persona)

@api.route('/accounts/preview_receipt', methods=['POST'])
@login_required
def _preview_receipt():
    from app.main.receipts import preview
    return func_call(preview, var('acct_id'), var('type_'))

@api.route('/admin/sessions/clear', methods=['GET','POST'])
@login_required
def clear_sessions():
    from app import clear_sessions
    return func_call(clear_sessions)

@api.route('/alice/welcome', methods=['POST'])
@login_required
def _send_welcome():
    from app.alice.outgoing import send_welcome
    return func_call(send_welcome, var('acct_id'))

@api.route('/alice/compose', methods=['POST'])
@login_required
def _compose():
    from app.alice.outgoing import compose
    return func_call(compose, var('body'), var('to'), mute=loads(var('mute')), acct_id=var('acct_id'))

@api.route('/alice/no_unread', methods=['POST'])
@login_required
def _no_unread():
    from app.alice.conversation import no_unread
    return func_call(no_unread, var('mobile'))

@api.route('/alice/chatlogs', methods=['POST'])
@login_required
def _get_chatlogs():
    from app.alice.conversation import get_messages
    return func_call(get_messages, mobile=var('mobile'), serialize=True)

@api.route('/alice/identify', methods=['POST'])
@login_required
def _identify():
    from app.alice.conversation import identify
    return func_call(identify, var('mobile'))

@api.route('/alice/toggle_reply_mute', methods=['POST'])
@login_required
def _toggle_mute():
    from app.alice.conversation import toggle_reply_mute
    return func_call(toggle_reply_mute, var('mobile'), loads(var('enabled')))

@api.route('/bravo/sessions/clear', methods=['GET', 'POST'])
@login_required
def _clear_sessions():
    from app import clear_sessions
    return func_call(clear_sessions)

@api.route('/booker/create', methods=['POST'])
@login_required
def _book_acct():
    from app.booker.book import make
    return func_call(make)

@api.route('/booker/search', methods=['POST'])
@login_required
def _search_bookings():
    from app.booker.search import search
    return func_call(search, var('query'), radius=var('radius'), weeks=var('weeks'))

@api.route('/cache/gifts', methods=['GET', 'POST'])
@login_required
def _api_cache_gifts():
    from app.main.tasks import cache_gifts
    return task_call(cache_gifts)

@api.route('/gifts/get', methods=['POST'])
@login_required
def _get_gifts():
    from app.main.cache import get_gifts
    from datetime import time, date
    print 'start=%s (type=%s), end=%s (type=%s)' %(var('start'),type(var('start')), var('end'), type(var('end')))
    return func_call(
        get_gifts,
        date.fromtimestamp(int(var('start'))),
        date.fromtimestamp(int(var('end'))))

@api.route('/group/conf/get', methods=['POST'])
@login_required
def _get_group_conf():
    from app.main import agency
    return func_call(agency.get_conf)

@api.route('/group/conf/update', methods=['POST'])
@login_required
def _update_group_conf():
    from app.main import agency
    return func_call(agency.update_conf, var('data'))

@api.route('/group/properties/get', methods=['POST'])
@login_required
def _get_admin_prop():
    from app.main.agency import get_admin_prop
    return func_call(get_admin_prop)

@api.route('/maps/get', methods=['POST'])
@login_required
def _get_maps():
    from app.main.maps import get_maps
    return func_call(get_maps)

@api.route('/maps/update', methods=['POST'])
@login_required
def _update_maps():
    from app.booker.tasks import update_maps
    return task_call(update_maps, group=g.group)

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
    from app.notify.events import create_event
    return func_call(create_event)

@api.route('/notify/events/cancel', methods=['POST'])
@login_required
def _cancel_event():
    from app.notify.events import cancel_event
    return func_call(cancel_event, evnt_id=var('evnt_id'))

@api.route('/notify/events/preview/token', methods=['POST'])
@login_required
def _preview_token():
    from app.notify.voice import get_token
    return func_call(get_token)

@api.route('/notify/events/dump', methods=['POST'])
@login_required
def _dump_event():
    from app.notify.events import dump_event
    return func_call(dump_event, evnt_id=var('evnt_id'))

@api.route('/notify/events/reset', methods=['POST'])
@login_required
def _reset_event():
    from app.notify.events import reset_event
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
    from app.notify.events import rmv_notifics
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
    from app.main.etapestry import get_query
    return func_call(get_query, var('name'), category=var('category'))

@api.route('/query/block_size', methods=['POST'])
@login_required
def _block_size():
    from app.main.etapestry import block_size
    return func_call(block_size, var('category'), var('query'))

@api.route('/query/route_size', methods=['POST'])
@login_required
def _route_size():
    from app.main.etapestry import route_size
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
    return func_call(get_logs,
        groups=loads(var('groups')), levels=loads(var('levels')), tags=loads(var('tags')))

@api.route('/tasks/backup_db', methods=['GET', 'POST'])
@login_required
def _backup_db():
    from app.main.tasks import backup_mongo
    return task_call(backup_mongo)

@api.route('/tasks/analyze_zone', methods=['POST'])
@login_required
def _find_zone_accts():
    from app.main.tasks import find_zone_accounts
    return task_call(find_zone_accounts,
        zone=var('map_title'), blocks=loads(var('blocks')))

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
