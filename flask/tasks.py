from celery.schedules import crontab
from app import celery_app
from config import DB_NAME
from datetime import timedelta

from gsheets import add_signup, create_rfu
from reminders import check_jobs, send_calls, send_emails, cancel_pickup, set_no_pickup
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
CELERYD_TASK_TIME_LIMIT = 1000
CELERYD_CONCURRENCY = 1
CELERYBEAT_SCHEDULE = {
  'get_non_participants': {
    'task': 'scheduler.analyze_non_participants',
    'schedule': crontab(hour=7, minute=0, day_of_week='*'),
    'options': { 'queue': DB_NAME }
  },
  'check_jobs': {
    'task': 'reminders.check_jobs',
    'schedule': crontab(minute='*/5'),
    'options': { 'queue': DB_NAME }
  },
}
