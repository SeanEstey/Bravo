import os
import logging
import pymongo
from datetime import timedelta

# App
LOG_LEVEL = logging.INFO

LOG_FILE = 'log.log'
FROM_NUMBER= '+17804138846'
FROM_EMAIL= 'Empties to WINN <emptiestowinn@wsaf.ca>'
SMS_NUMBER = '+15874104251'
EMERGENCY_CONTACT='7808635715'
CALLER_ID= 'Winnifred Stewart Association'
MAX_ATTEMPTS= 2
REDIAL_DELAY = 300
SCHEDULE_FREQUENCY = 300
UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = set(['csv','xls'])
TEMPLATE = {
  'etw_reminder': [
    {'header': 'Name', 'field': 'name'},
    {'header': 'Phone', 'field': 'to'},
    {'header': 'Status', 'field': 'status'},
    {'header': 'Next P/U Date', 'field': 'event_date'},
    {'header': 'Office Notes', 'field': 'office_notes'}
  ],
  'gg_delivery': [
    {'header': 'Name', 'field': 'name'},
    {'header': 'Phone', 'field': 'to'},
    {'header': 'Date', 'field': 'event_date'},
    {'header': 'Price', 'field': 'price'}
  ],
  'special_msg': [
    {'header': 'Name', 'field': 'name'},
    {'header': 'Phone', 'field': 'to'}
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
    'task': 'tasks.run_scheduler',
    'schedule': timedelta(seconds=SCHEDULE_FREQUENCY)
  },
}

# Ports/Domains
PUB_DOMAIN = 'http://seanestey.ca'
MONGO_URL = 'localhost'
MONGO_PORT = 27017
MAILGUN_DOMAIN = 'wsaf.ca'

formatter = logging.Formatter('[%(asctime)s] %(message)s','%m-%d %H:%M')
