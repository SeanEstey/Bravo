'''app.api.manager'''
from json import dumps, loads
from flask import g, Response, request, jsonify
from flask_login import current_user
import celery.result
from app.lib.utils import start_timer, end_timer, formatter
from logging import getLogger
log = getLogger(__name__)

def WRITE_ME(msg=None):
    return msg or 'NOT YET IMPLEMENTED'

#-------------------------------------------------------------------------------
def func_call(function, *args, **kwargs):
    s = start_timer()

    try:
        rv = function(*args, **kwargs)
    except Exception as e:
        log.exception('API function "%s" failed', function.__name__)
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

    log.debug('API call success, func=%s (%s)', name, end_timer(dt))

    try:
        json_rv = formatter({'status':'success', 'data':rv}, bson_to_json=True, to_json=True)
    except Exception as e:
        log.debug('rv is not serializable.')
        json_rv = dumps({'status':'success', 'data':'return value not serializable'})

    return Response(
        response=json_rv, status=200,mimetype='application/json')

#-------------------------------------------------------------------------------
def get_var(k):
    #log.debug(request.form.to_dict())

    if request.method == 'GET':
        return request.args.get(k)
    elif request.method == 'POST':
        return request.form.get(k)
