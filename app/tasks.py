'''app.tasks'''

import logging
import os
from time import sleep
import traceback as tb
from celery.task.control import revoke
from celery.signals import task_prerun, task_postrun
from celery.utils.log import get_task_logger
from bson.objectid import ObjectId as oid
from flask_socketio import SocketIO
from etap import EtapError
from utils import bcolors, print_vars
from flask import g, has_app_context, has_request_context, request
from . import celery, celery_sio, mongodb, get_db, utils, create_app, celery_app, deb_hand,\
inf_hand, err_hand, exc_hand
from uber_task import UberTask

log = get_task_logger(__name__)
log.addHandler(err_hand)
log.addHandler(inf_hand)
log.addHandler(deb_hand)
log.addHandler(exc_hand)
log.setLevel(logging.DEBUG)
celery_app(create_app('app', kv_sess=False))

# Import tasks defined in blueprints
from app.main.tasks import add_gsheets_signup, non_participants, rfu,\
send_receipts, update_accts_sms
from app.booker.tasks import update_maps
from app.routing.tasks import analyze_routes, build_route, build_routes
from app.notify.tasks import monitor_triggers, fire_trigger, schedule_reminders, skip_pickup

#-------------------------------------------------------------------------------
@task_prerun.connect
def task_prerun(signal=None, sender=None, task_id=None, task=None, *args, **kwargs):
    '''Dispatched before a task is executed by Task obj.
    Sender == Task.
    @args, @kwargs: the tasks positional and keyword arguments
    '''

    kwargs['kwargs'][UberTask.ENVIRON_KW] = {}

    for var in celery.app.config['ENV_VARS']:
        kwargs['kwargs'][UberTask.ENVIRON_KW][var] = os.environ.get(var, '')

    #print 'prerun=%s, kwargs=%s' % (sender.name.split('.')[-1], kwargs)
    pass

#-------------------------------------------------------------------------------
@task_postrun.connect
def task_postrun(signal=None, sender=None, task_id=None, task=None, retval=None,\
state=None, *args, **kwargs):
    '''Dispatched after a task has been executed by Task obj.
    @Sender: the task object executed.
    @task_id: Id of the task to be executed. (meaning the next one in the queue???)
    @task: The task being executed.
    @args: The tasks positional arguments.
    @kwargs: The tasks keyword arguments.
    @retval: The return value of the task.
    @state: Name of the resulting state.
    '''

    name = sender.name.split('.')[-1]

    if state != 'SUCCESS':
        log.error('task=%s error. state=%s, retval=%s', name, state, retval)
        log.debug('task=%s failure.', name, exc_info=True)
    else:
        print 'postrun=%s, state=%s' % (name, state)

#-------------------------------------------------------------------------------
def kill(task_id):
    log.info('attempting to kill task_id %s', task_id)

    try:
        response = celery.control.revoke(task_id, terminate=True)
    except Exception as e:
        log.error('revoke task error: %s', str(e))
        return False

    log.info('revoke response: %s', str(response))

    return response
