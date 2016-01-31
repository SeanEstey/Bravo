import os
import logging
import pymongo
from datetime import timedelta
from server_settings import DB_NAME

# App
LOG_LEVEL = logging.INFO

LOG_FILE = 'log'
FROM_NUMBER= '+17804138846'
FROM_EMAIL= 'Empties to WINN <emptiestowinn@wsaf.ca>'
SMS_NUMBER = '+15874104251'
EMERGENCY_CONTACT='7808635715'
CALLER_ID= 'Winnifred Stewart Association'
MAX_ATTEMPTS= 2
REDIAL_DELAY = 300
SCHEDULE_FREQUENCY = 30
UPLOAD_FOLDER = '/tmp'
JOBS_PER_PAGE = 10
ALLOWED_EXTENSIONS = set(['csv','xls'])
TEMPLATE = {
  'etw_reminder': [
    {'header': 'Account', 'field': 'account', 'hide': True},
    {'header': 'Name', 'field': 'name'},
    {'header': 'Phone', 'field': 'to', 'status_field': 'call_status'},
    {'header': 'Email', 'field': 'email', 'status_field': 'email_status'},
    {'header': 'Block', 'field': 'block', 'hide': True},
    {'header': 'Status', 'field': 'status'},
    {'header': 'Next P/U Date', 'field': 'event_date'},
    {'header': 'Office Notes', 'field': 'office_notes'}
  ],
  'gg_delivery': [
    {'header': 'Name', 'field': 'name'},
    {'header': 'Phone', 'field': 'to', 'status_field': 'call_status'},
    {'header': 'Date', 'field': 'event_date'},
    {'header': 'Price', 'field': 'price'}
  ],
  'announce_text': [
    {'header': 'Name', 'field': 'name'},
    {'header': 'Phone', 'field': 'to', 'status_field': 'call_status'}
  ],
  'announce_voice': [
    {'header': 'Name', 'field': 'name'},
    {'header': 'Phone', 'field': 'to', 'status_field': 'call_status'}
  ]
}

# Celery
BROKER_URI= 'amqp://'
CELERY_BROKER_URL = 'amqp://'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Canada/Mountain'
CELERY_ENABLE_UTC = False
CELERYD_CONCURRENCY = 1
CELERYBEAT_SCHEDULE = {
  'bravo_scheduler': {
    'task': 'reminders.run_scheduler',
    'schedule': timedelta(seconds=SCHEDULE_FREQUENCY),
    'options': { 'queue': DB_NAME }
  },
}

# Ports/Domains
MONGO_URL = 'localhost'
MONGO_PORT = 27017
MAILGUN_DOMAIN = 'wsaf.ca'

formatter = logging.Formatter('[%(asctime)s] %(message)s','%m-%d %H:%M')
