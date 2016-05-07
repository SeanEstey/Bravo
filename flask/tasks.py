from celery.schedules import crontab
from celery import Celery
from datetime import timedelta

#-------------------------------------------------------------------------------
def make_celery(app):
    CELERY_BROKER_URL = 'amqp://'
    celery = Celery(app.name, broker=CELERY_BROKER_URL)
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

#from config import DB
from app import app

celery_app = make_celery(app)
celery_app.config_from_object('tasks')

# Load in registered functions
from gsheets import add_signup, create_rfu
from reminders import monitor_jobs, send_calls, send_emails, cancel_pickup, set_no_pickup
from receipts import process
from scheduler import analyze_non_participants

# Celery
BROKER_URI= 'amqp://'
CELERY_BROKER_URL = 'amqp://'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Canada/Mountain'
CELERY_ENABLE_UTC = False
CELERYD_TASK_TIME_LIMIT = 3000
CELERYD_CONCURRENCY = 1
CELERYBEAT_SCHEDULE = {
  'get_non_participants': {
    'task': 'scheduler.analyze_non_participants',
    'schedule': crontab(hour=7, minute=0, day_of_week='*'),
    'options': { 'queue': app.config['DB'] }
  },
  'check_jobs': {
    'task': 'reminders.monitor_jobs',
    'schedule': crontab(minute='*/5'),
    'options': { 'queue': app.config['DB'] }
  },
}
