import os
import logging
import pymongo
from datetime import timedelta
from private_config import *
from celery.schedules import crontab

# Flask
# When True, uses gevent web server. Server auto-restarts
# on code changes
# When False, uses Wekzeug dev server
DEBUG = False

TEST_MODE = False

if DEBUG == True:
    LOG_LEVEL = logging.DEBUG
else:
    LOG_LEVEL = logging.INFO

if TEST_MODE == True:
    DB_NAME = 'test'
    ROUTE_IMPORTER_SHEET = 'Test Route Importer'
else:
    DB_NAME = 'wsf'
    ROUTE_IMPORTER_SHEET = 'Route Importer'

# App
LOCAL_PORT = 8000
LOCAL_URL = 'http://localhost:8000'
PUB_URL = 'http://bravoweb.ca'
TITLE = 'Bravo'
LOG_FILE = 'logs/log'
formatter = logging.Formatter('[%(asctime)s] %(message)s','%m-%d %H:%M')


# Reminders
FROM_NUMBER= '+17804138846'
SMS_NUMBER = '+15874104251'
EMERGENCY_CONTACT='7808635715'
CALLER_ID= 'Winnifred Stewart Association'
MAX_ATTEMPTS= 2
REDIAL_DELAY = 300
UPLOAD_FOLDER = '/tmp'
JOBS_PER_PAGE = 10
ALLOWED_EXTENSIONS = set(['csv','xls'])

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
  #'check_reminder_jobs': {
  #  'task': 'reminders.check_jobs',
  #  'schedule': timedelta(seconds=30),
  #  'options': { 'queue': DB_NAME }
  #},
  'get_non_participants': {
    'task': 'scheduler.analyze_non_participants',
    'schedule': crontab(hour=7, minute=0, day_of_week='*'),
    'options': { 'queue': DB_NAME }
  }
}

# Ports/Domains
MONGO_URL = 'localhost'
MONGO_PORT = 27017

# Mailgun
MAILGUN_DOMAIN = 'wsaf.ca'
FROM_EMAIL= 'Empties to WINN <emptiestowinn@wsaf.ca>'

# PHP
ETAP_WRAPPER_URL = 'http://www.bravoweb.ca/etap/views.php'
