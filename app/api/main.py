'''app.api.main'''
import logging
from json import dumps, loads
from flask import Response, request, jsonify
from flask_login import current_user
import celery.result
from app import get_logger
from app.lib.utils import start_timer, end_timer, formatter
log = get_logger('api.main')

def WRITE_ME(msg=None):
    return msg or 'NOT YET IMPLEMENTED'

#-------------------------------------------------------------------------------
def func_call(function, *args, **kwargs):
    s = start_timer()

    try:
        rv = function(*args, **kwargs)
    except Exception as e:
        return build_resp(exc=str(e))
    return build_resp(rv=rv, name=function.__name__, dt=s)

#-------------------------------------------------------------------------------
def task_call(function, *args, **kwargs):
    try:
        rv = function.delay(*args, **kwargs)
    except Exception as e:
        log.error('task failed')
        log.error('%s failed. desc=%s', function.__name__, str(e))
        log.debug('', exc_info=True)
        return build_resp(exc=str(e))

    return build_resp(rv=rv)

#-------------------------------------------------------------------------------
def build_resp(rv=None, exc=False, name=None, dt=None):
    '''Returns JSON obj: {"status": <str>, "desc": <failure str>, "data": <str/dict/list>}
    '''

    if exc:
        log.error('api call fail. desc=%s', exc)
        log.debug('',exc_info=True)

        return Response(
            response=dumps({'status':'failed','desc':exc}),
            status=500, mimetype='application/json')

    if rv and isinstance(rv, celery.result.AsyncResult):
        return Response(
            response=dumps({'status':'success','data':None}),
            status=200, mimetype='application/json')

    # Success

    duration = end_timer(dt)
    log.debug('API call success, func=%s (%ss)', name, duration)

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
