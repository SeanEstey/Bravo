'''app.tasks'''
import os
from logging import getLogger
from celery.task.control import revoke
from celery.signals import task_prerun, task_postrun, task_failure, task_revoked
from celery.signals import worker_process_init, worker_ready, worker_shutdown
from celery.signals import celeryd_init, celeryd_after_setup
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

@celeryd_init.connect
def foo_bar(**kwargs):
    print 'CELERYD_INIT'

@celeryd_after_setup.connect
def setup_direct_queue(sender, instance, **kwargs):
    print 'CELERYD_AFTER_SETUP'

@worker_ready.connect
def do_something(**kwargs):
    '''Called by parent worker process'''

    print 'WORKER_READY'
    from logging import DEBUG
    from app.lib.mongo_log import BufferedMongoHandler
    from db_auth import user, password
    authenticate(db_client)
    mongo_handler = BufferedMongoHandler(
        level=DEBUG,
        mongo_client=db_client,
        connect=True,
        db_name='bravo',
        user=user,
        pw=password)
    app.logger.addHandler(mongo_handler)
    mongo_handler.init_buf_timer()

@worker_shutdown.connect
def shutting_down(**kwargs):
    print 'WORKER_SHUTTING_DOWN'

#-------------------------------------------------------------------------------
@worker_process_init.connect
def pool_worker_init(**kwargs):
    '''Called by each child worker process (forked)'''

    from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

    authenticate(db_client)

    # Set root logger for this child process
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
        level=DEBUG,
        mongo_client = db_client,
        connect=True,
        db_name='bravo',
        user=user,
        pw=password)
    buf_mongo_handler.init_buf_timer()
    logger.addHandler(buf_mongo_handler)

    print 'Celery PoolWorker initialized. PID %s' % os.getpid()

#-------------------------------------------------------------------------------
@task_prerun.connect
def task_prerun(signal=None, sender=None, task_id=None, task=None, *args, **kwargs):
    '''Dispatched before a task is executed by Task obj.
    Sender == Task.
    @args, @kwargs: the tasks positional and keyword arguments
    '''

    print 'RECEIVED TASK %s' % sender.name.split('.')[-1]
    global timer
    timer = start_timer()

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

    for handler in getLogger('app').handlers:
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
    app.logger.error('Task %s failed. Click for more info.', name,
        extra={'exception':str(exception), 'traceback':traceback})

#-------------------------------------------------------------------------------
@task_revoked.connect
def task_revoke(sender=None, task_id=None, request=None, terminated=None, signum=None, expired=None, *args, **kwargs):
    '''Called by worker parent. Task is revoked and child worker is also
    terminated. A new child worker will spawn, causing Mongo fork warnings.
    '''

    from app.lib.utils import dump, print_vars
    name = sender.name.split('.')[-1]
    str_req = print_vars(request)
    app.logger.warning('Task %s revoked', name, extra={'request':str_req})
