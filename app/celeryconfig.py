from celery.schedules import crontab
from app import app

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
    'task': 'app.tasks.analyze_non_participants',
    'schedule': crontab(hour=6, minute=00, day_of_week='*'),
    'options': { 'queue': app.config['DB'] }
  },
  'update_sms_accounts': {
      'task': 'app.tasks.update_scheduled_accounts_for_sms',
      'schedule': crontab(hour=5, minute=00, day_of_week='*'),
      'options': { 'queue': app.config['DB'] }
  },
  'setup_reminders': {
      'task': 'app.tasks.setup_reminder_jobs',
      'schedule': crontab(hour=7, minute=00, day_of_week='*'),
      'options': { 'queue': app.config['DB'] }
  },
  'create_routes': {
      'task': 'app.tasks.build_todays_routes',
      'schedule': crontab(hour=7, minute=10, day_of_week='*'),
      'options': { 'queue': app.config['DB'] }
  },
  'check_triggers': {
    'task': 'app.tasks.monitor_triggers',
    'schedule': crontab(minute='*/1'),
    'options': { 'queue': app.config['DB'] }
  }
}
