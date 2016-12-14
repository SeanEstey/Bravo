from celery.schedules import crontab
import config

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
  'find_non_participants': {
    'task': 'app.tasks.find_non_participants',
    'schedule': crontab(hour=8, minute=40, day_of_week='*'),
    'options': { 'queue': config.DB }
  },
  'update_sms_accounts': {
      'task': 'app.tasks.update_sms_accounts',
      'schedule': crontab(hour=5, minute=00, day_of_week='*'),
      'options': { 'queue': config.DB }
  },
  'schedule_reminders': {
      'task': 'app.tasks.schedule_reminders',
      'schedule': crontab(hour=7, minute=00, day_of_week='*'),
      'options': { 'queue': config.DB }
  },
  'build_routes': {
      'task': 'app.tasks.build_scheduled_routes',
      'schedule': crontab(hour=6, minute=30, day_of_week='*'),
      'options': { 'queue': config.DB }
  },
  'monitor_triggers': {
    'task': 'app.tasks.monitor_triggers',
    'schedule': crontab(minute='*/5'),
    'options': { 'queue': config.DB }
  },
  'update_maps': {
    'task': 'app.tasks.update_maps',
    'schedule': crontab(hour=7, minute=10, day_of_week='*'),
    'options': { 'queue': config.DB}
  }
}
