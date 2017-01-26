'''app.api.main'''
import logging
from json import dumps
from flask import Response, request, jsonify
import celery.result
from app.utils import start_timer, end_timer
log = logging.getLogger(__name__)

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
    rv = function.delay(*args, **kwargs)
    return build_resp(rv=rv)

#-------------------------------------------------------------------------------
def build_resp(rv=None, exc=False, name=None, dt=None):
    if exc:
        log.error('api call fail. desc=%s', exc)
        log.debug('',exc_info=True)

        return Response(
            response=dumps({'status':'failed','desc':exc}),
            status=500, mimetype='application/json')

    if rv and isinstance(rv, celery.result.AsyncResult):
        if rv.state == 'SUCCESS':
            end_timer(dt, display=True, lbl='API call success, func="%s"' % name)

            return Response(
                response=dumps({'status':'success','data':None}),
                status=200, mimetype='application/json')
        elif rv.state == 'FAILURE':
            log.error('api celery task fail. desc=%s', rv.result)
            log.debug('trace=%s', rv.traceback)

            return Response(
                response=dumps({'status':'failure', 'desc':dumps(rv.result), 'data':None}),
                status=200, mimetype='application/json')

    end_timer(dt, display=True, lbl='API call success, func="%s"' % name)

    return Response(
        response=dumps({'status':'success', 'data':rv}),
        status=200,mimetype='application/json')

#-------------------------------------------------------------------------------
def get_var(k):
    if request.method == 'GET':
        return request.args.get(k)
    elif request.method == 'POST':
        return request.form.get(k)