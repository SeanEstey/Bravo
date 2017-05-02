'''app.tasks'''
import os
from celery.task.control import revoke
from celery.signals import task_prerun, task_postrun, task_failure
from app import create_app, init_celery
from app import celery as _celery
from app.lib.loggy import Loggy
from app.lib.utils import inspector, start_timer, end_timer

timer = None
app = create_app(__name__, kv_sess=False)
celery = init_celery(app)

# Import all tasks for worker
from app.main.tasks import *
from app.booker.tasks import *
from app.notify.tasks import *

log = Loggy('tasks', celery_task=True)

#-------------------------------------------------------------------------------
@task_prerun.connect
def task_prerun(signal=None, sender=None, task_id=None, task=None, *args, **kwargs):
    '''Dispatched before a task is executed by Task obj.
    Sender == Task.
    @args, @kwargs: the tasks positional and keyword arguments
    '''

    global timer
    timer = start_timer()
    #log.debug('prerun=%s, request=%s', sender.name.split('.')[-1], '...')

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

    global timer
    name = sender.name.split('.')[-1]

    if state != 'SUCCESS':
        log.error('task=%s error. state=%s, retval=%s', name, state, retval)
        log.exception('task=%s failure (%s)', name, end_timer(timer))
    else:
        pass
        #log.debug('%s: state=%s, retval="%s" (%s)', name, state, retval, duration)

#-------------------------------------------------------------------------------
@task_failure.connect
def task_failure(signal=None, sender=None, task_id=None, exception=None, traceback=None, *args, **kwargs):
    name = sender.name.split('.')[-1]
    log.error('task=%s failed. exception=%s', name, exception)
    log.debug('exception: %s', traceback)

#-------------------------------------------------------------------------------
def kill(task_id):
    log.info('attempting to kill task_id %s', task_id)

    try:
        response = revoke(task_id, terminate=True)
    except Exception as e:
        log.error('revoke task error: %s', str(e))
        return False

    log.info('revoke response: %s', str(response))

    return response
