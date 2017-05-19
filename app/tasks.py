'''app.tasks'''
import os
from logging import getLogger, DEBUG, INFO, WARNING, ERROR, CRITICAL
from celery.task.control import revoke
from celery.signals import task_prerun, task_postrun, task_failure, worker_process_init
from app import create_app, colors as c, celery
from app.lib.mongodb import create_client, authenticate
from app.lib.utils import inspector, start_timer, end_timer
from uber_task import UberTask
import celeryconfig

# Pre-fork vars
app = create_app(__name__, kv_sess=False, mongo_client=False)
UberTask.flsk_app = app
celery.config_from_object(celeryconfig)
db_client = create_client(connect=False, auth=False)
UberTask.db_client = db_client
celery.Task = UberTask
timer = None
print 'Celery app initialized for PID %s' % os.getpid()

# Import all tasks for worker
from app.main.tasks import *
from app.booker.tasks import *
from app.notify.tasks import *

#-------------------------------------------------------------------------------
@worker_process_init.connect
def pool_worker_init(**kwargs):
    '''Post-fork code per pool worker.'''

    authenticate(db_client)

    # Root celery logger for this process
    logger = getLogger('app')
    logger.setLevel(DEBUG)

    from app.lib.mongo_log import file_handler, BufferedMongoHandler
    from db_auth import user, password
    from config import LOG_PATH as path

    logger.addHandler(file_handler(DEBUG, '%sdebug.log'%path, color=c.WHITE))
    logger.addHandler(file_handler(INFO, '%sevents.log'%path, color=c.GRN))
    logger.addHandler(file_handler(WARNING, '%sevents.log'%path, color=c.YLLW))
    logger.addHandler(file_handler(ERROR, '%sevents.log'%path, color=c.RED))
    buf_mongo_handler = BufferedMongoHandler(
        level=INFO,
        mongo_client = db_client,
        connect=True,
        db_name='bravo',
        user=user,
        pw=password)
    buf_mongo_handler.init_buf_timer()
    logger.addHandler(buf_mongo_handler)

    print 'Initialized MongoHandler for PID %s' % os.getpid()

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

    # Force log flush to Mongo if timer set since thread timer seems to sleep after task is complete.
    from app.lib.mongo_log import BufferedMongoHandler

    #for handler in getLogger('worker').handlers:
    for handler in getLogger('app').handlers: #__name__).handlers:
        if isinstance(handler, BufferedMongoHandler) and handler.buf_flush_tim:
            if not handler.test_connection():
                handler._connect()
            handler.flush_to_mongo()

    '''
    if state != 'SUCCESS':
        log.error('task=%s error. state=%s, retval=%s', name, state, retval)
        log.exception('task=%s failure (%s)', name, end_timer(timer))
    else:
        pass
        #log.debug('%s: state=%s, retval="%s" (%s)', name, state, retval, duration)
    '''

#-------------------------------------------------------------------------------
@task_failure.connect
def task_failure(signal=None, sender=None, task_id=None, exception=None, traceback=None, *args, **kwargs):

    name = sender.name.split('.')[-1]
    print 'Task %s failed' % name
    #log.error('Task %s failed. Click for more info.', name,
    #    extra={'exception':exception, 'traceback':traceback})

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
