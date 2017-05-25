'''app.api.manager'''
from json import dumps, loads
from flask import g, Response, request, jsonify
from flask_login import current_user
import celery.result
from app.lib.utils import start_timer, end_timer, formatter
from logging import getLogger
log = getLogger(__name__)

headers = [
    "Content-Length",
    "X-Forwarded-For",
    "Connection",
    "Accept",
    "Host",
    "X-Forwarded-Proto",
    "X-Real-Ip",
    "Content-Type",
    "Authorization"
]

def WRITE_ME(msg=None):
    return msg or 'NOT YET IMPLEMENTED'

#-------------------------------------------------------------------------------
def func_call(function, *args, **kwargs):
    s = start_timer()

    try:
        rv = function(*args, **kwargs)
    except Exception as e:
        log.exception('API function "%s" failed', function.__name__,
            extra={'request':dump_request()})
        return build_resp(exc=e)

    return build_resp(rv=rv, name=function.__name__, dt=s)

#-------------------------------------------------------------------------------
def task_call(function, *args, **kwargs):
    try:
        rv = function.delay(*args, **kwargs)
    except Exception as e:
        log.exception('API task "%s" failed', function.__name__)
        return build_resp(exc=e)

    return build_resp(rv=rv)

#-------------------------------------------------------------------------------
def build_resp(rv=None, exc=None, name=None, dt=None):
    '''Returns JSON obj: {"status": <str>, "desc": <failure str>, "data": <str/dict/list>}
    '''

    if exc:
        return Response(
            response=dumps({'status':'failed','desc':str(exc)}),
            status=500, mimetype='application/json')

    if rv and isinstance(rv, celery.result.AsyncResult):
        return Response(
            response=dumps({'status':'success','data':None}),
            status=200, mimetype='application/json')

    # Success

    try:
        json_rv = formatter({'status':'success', 'data':rv}, bson_to_json=True, to_json=True)
    except Exception as e:
        log.debug('rv is not serializable.')
        json_rv = dumps({'status':'success', 'data':'return value not serializable'})

    resp = Response(response=json_rv, status=200,mimetype='application/json')

    if "logger" not in request.path:
        log.debug('%s success', request.path,
            extra={
                'request':dump_request(),
                'duration': end_timer(dt),
                'function':name,
                'response': dump_response(resp)})

    return resp

#-------------------------------------------------------------------------------
def get_var(k):

    if request.method != 'POST':
        raise Exception("Only POST requests allowed with API")

    if request.headers["Content-Type"] == "application/json":
        from json import loads
        json_data = request.json
        v = json_data[k]
        return v
    else:
        return request.form.get(k, None)

#-------------------------------------------------------------------------------
def dump_headers(obj):

    _headers = {}
    for name in headers:
        if obj.get(name):
            _headers[name] = obj[name]
    return _headers

#-------------------------------------------------------------------------------
def dump_request():
    return {
        'url': request.url,
        'headers': dump_headers(request.headers),
        'json_data': request.json,
        'form_data': request.form.to_dict(),
        'request_data': request.data
    }

#-------------------------------------------------------------------------------
def dump_response(resp):

    return {
        'headers': dump_headers(dict(resp.headers)),
        'status': resp._status,
        'data': str(resp.response)[0:50]+ ' ...'

    }
