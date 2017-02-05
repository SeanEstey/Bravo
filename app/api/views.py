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

@api.route('/properties/get', methods=['POST'])
@login_required
def call_op_stats():
    return func_call(get_op_stats)

@api.route('/accounts/get', methods=['POST'])
@login_required
def call_accts_get():
    return func_call(donors.get, get_var('acct_id'))

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

@api.route('/signups/lookup', methods=['POST'])
@login_required
def call_phone_lookup():
    return func_call(lookup_carrier, get_var('phone'))

@api.route('/routing/build', methods=['POST'])
@login_required
def call_route_build():
    from app.routing.tasks import build_route
    return task_call(build_route, get_var('route_id'), job_id=get_var('job_id'))

@api.route('/routing/edit', methods=['POST'])
@login_required
def call_route_edit():
    return func_call(edit_field, get_var('route_id'), get_var('field'), get_var('value'))














#-------------------------------------------------------------------------------
'''
Informational - 1xx
This class of status code indicates a provisional response. There are no 1xx status codes used in REST framework by default.

HTTP_100_CONTINUE
HTTP_101_SWITCHING_PROTOCOLS
Successful - 2xx
This class of status code indicates that the clients request was successfully received, understood, and accepted.

HTTP_200_OK
HTTP_201_CREATED
HTTP_202_ACCEPTED
HTTP_203_NON_AUTHORITATIVE_INFORMATION
HTTP_204_NO_CONTENT
HTTP_205_RESET_CONTENT
HTTP_206_PARTIAL_CONTENT
Redirection - 3xx
This class of status code indicates that further action needs to be taken by the user agent in order to fulfill the request.

HTTP_300_MULTIPLE_CHOICES
HTTP_301_MOVED_PERMANENTLY
HTTP_302_FOUND
HTTP_303_SEE_OTHER
HTTP_304_NOT_MODIFIED
HTTP_305_USE_PROXY
HTTP_306_RESERVED
HTTP_307_TEMPORARY_REDIRECT
Client Error - 4xx
The 4xx class of status code is intended for cases in which the client seems to have erred. Except when responding to a HEAD request, the server SHOULD include an entity containing an explanation of the error situation, and whether it is a temporary or permanent condition.

HTTP_400_BAD_REQUEST
HTTP_401_UNAUTHORIZED
HTTP_402_PAYMENT_REQUIRED
HTTP_403_FORBIDDEN
HTTP_404_NOT_FOUND
HTTP_405_METHOD_NOT_ALLOWED
HTTP_406_NOT_ACCEPTABLE
HTTP_407_PROXY_AUTHENTICATION_REQUIRED
HTTP_408_REQUEST_TIMEOUT
HTTP_409_CONFLICT
HTTP_410_GONE
HTTP_411_LENGTH_REQUIRED
HTTP_412_PRECONDITION_FAILED
HTTP_413_REQUEST_ENTITY_TOO_LARGE
HTTP_414_REQUEST_URI_TOO_LONG
HTTP_415_UNSUPPORTED_MEDIA_TYPE
HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE
HTTP_417_EXPECTATION_FAILED
HTTP_428_PRECONDITION_REQUIRED
HTTP_429_TOO_MANY_REQUESTS
HTTP_431_REQUEST_HEADER_FIELDS_TOO_LARGE
Server Error - 5xx
Response status codes beginning with the digit 5 indicate cases in which the server is aware that it has erred or is incapable of performing the request. Except when responding to a HEAD request, the server SHOULD include an entity containing an explanation of the error situation, and whether it is a temporary or permanent condition.

HTTP_500_INTERNAL_SERVER_ERROR
HTTP_501_NOT_IMPLEMENTED
HTTP_502_BAD_GATEWAY
HTTP_503_SERVICE_UNAVAILABLE
HTTP_504_GATEWAY_TIMEOUT
HTTP_505_HTTP_VERSION_NOT_SUPPORTED
HTTP_511_NETWORK_AUTHENTICATION_REQUIRED
'''
