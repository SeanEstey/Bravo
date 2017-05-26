'''app.tasks'''
import os
from logging import getLogger
from flask_login import current_user
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
app = create_app('app', kv_sess=False, mongo_client=False)
UberTask.flsk_app = app
celery.config_from_object(celeryconfig)
db_client = create_client(connect=False, auth=False)
UberTask.db_client = db_client
celery.Task = UberTask
timer = None

@celeryd_init.connect
def _celeryd_init(**kwargs):
    print 'CELERYD_INIT'

@celeryd_after_setup.connect
def _celeryd_after_setup(sender, instance, **kwargs):
    print 'CELERYD_AFTER_SETUP'

@worker_ready.connect
def _parent_worker_ready(**kwargs):
    '''Called by parent worker process'''

    from logging import WARNING
    from app.lib.mongo_log import BufferedMongoHandler
    from db_auth import user, password
    authenticate(db_client)
    mongo_handler = BufferedMongoHandler(
        level=WARNING,
        mongo_client=db_client,
        connect=True,
        db_name='bravo',
        user=user,
        pw=password)
    app.logger.addHandler(mongo_handler)
    mongo_handler.init_buf_timer()
    print 'WORKER_READY. PID %s' % os.getpid()

@worker_shutdown.connect
def _parent_worker_shutdown(**kwargs):
    print 'WORKER_SHUTTING_DOWN'

#-------------------------------------------------------------------------------
@worker_process_init.connect
def _child_worker_init(**kwargs):
    '''Called by each child worker process (forked)'''

    from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Experimental
    global celery
    db_client = create_client()
    UberTask.db_client = db_client
    celery.Task = UberTask

    #authenticate(db_client)

    # Set root logger for this child process
    logger = getLogger('app')
    logger.setLevel(DEBUG)

    from app.lib.mongo_log import file_handler, BufferedMongoHandler
    from db_auth import user, password
    from config import LOG_PATH as path

    buf_mongo_handler = BufferedMongoHandler(
        level=DEBUG,
        mongo_client = db_client,
        connect=True,
        db_name='bravo',
        user=user,
        pw=password)
    buf_mongo_handler.init_buf_timer()
    logger.addHandler(buf_mongo_handler)

    print 'WORKER_CHILD_INIT. PID %s' % os.getpid()


#-------------------------------------------------------------------------------
@task_prerun.connect
def _child_task_prerun(signal=None, sender=None, task_id=None, task=None, *args, **kwargs):
    '''Dispatched before a task is executed by Task obj.
    Sender == Task.
    @args, @kwargs: the tasks positional and keyword arguments
    '''

    print 'RECEIVED TASK %s' % sender.name.split('.')[-1]
    global timer
    timer = start_timer()

#-------------------------------------------------------------------------------
@task_postrun.connect
def _child_task_postrun(signal=None, sender=None, task_id=None, task=None, retval=None,\
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

#-------------------------------------------------------------------------------
@task_failure.connect
def _child_task_failure(signal=None, sender=None, task_id=None, exception=None,
traceback=None, einfo=None, *args, **kwargs):

    name = sender.name.split('.')[-1]
    print 'TASK_FAILURE. NAME %s' % name
    app.logger.error('Task %s failed. Click for more info.', name,
        extra={
            'exception':str(exception),
            'traceback':str(traceback),
            'task_args': args,
            'task_kwargs': kwargs})

#-------------------------------------------------------------------------------
@task_revoked.connect
def _child_task_revoke(sender=None, task_id=None, request=None, terminated=None, signum=None, expired=None, *args, **kwargs):
    '''Called by worker parent. Task is revoked and child worker is also
    terminated. A new child worker will spawn, causing Mongo fork warnings.
    '''

    from app.lib.utils import dump, print_vars
    name = sender.name.split('.')[-1]
    str_req = print_vars(request)
    print 'TASK_REVOKED. NAME %s' % name
    app.logger.warning('Task %s revoked', name, extra={'request':str_req})
