import os
import logging
import pymongo
from datetime import timedelta

# Celery
BROKER_URI= 'amqp://'
CELERY_BROKER_URL = 'amqp://'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Canada/Mountain'
CELERY_ENABLE_UTC = False
#CELERY_MODULE = 'bravo'
CELERYBEAT_SCHEDULE = {
  'bravo_scheduler': {
    'task': 'server.run_scheduler',
    'schedule': timedelta(seconds=30)
  },
}


# Ports/Domains
PUB_DOMAIN = 'http://seanestey.ca'
PREFIX = '/bravo'
LOCAL_DEPLOY_PORT = 8000
PUB_DEPLOY_PORT = 80
LOCAL_TEST_PORT = 5000
PUB_TEST_PORT = 8080
MONGO_URL = 'localhost'
MONGO_PORT = 27017
LOG_LEVEL = logging.INFO
LOG_FILE = 'log.log'
TEST_DB = 'test'
DEPLOY_DB = 'wsf'
MAILGUN_DOMAIN = 'wsaf.ca'

# Twilio
FROM_NUMBER= '+17804138846'
TWILIO_NUMBER = '+15874104251'
SMS_NUMBER='17808093927'
EMERGENCY_CONTACT='7808635715'
CALLER_ID= 'Winnifred Stewart Association'
CPS= 1
MAX_ATTEMPTS= 1
REDIAL_DELAY = 60

# App
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

