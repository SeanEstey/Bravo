import os
import logging
import pymongo
from datetime import timedelta
from private_config import *

# When True, uses Werkzeug dev server. Server auto-restarts on code changes
# When False, uses gevent (wsgi, threaded) web server.
DEBUG = False

if DEBUG == True:
    LOG_LEVEL = logging.DEBUG
else:
    LOG_LEVEL = logging.INFO

TEST_DATA = True

if TEST_DATA == True:
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
LOG_FILE = '/var/www/bravo/logs/log.log'
LOG_LINES = 200

# Reminders
JOB_TIME_LIMIT = 3000
FROM_NUMBER= '+17804138846'
SMS_NUMBER = '+15874104251'
EMERGENCY_CONTACT='7808635715'
CALLER_ID= 'Winnifred Stewart Association'
MAX_CALL_ATTEMPTS= 2
REDIAL_DELAY = 300
UPLOAD_FOLDER = '/tmp'
JOBS_PER_PAGE = 10
ALLOWED_EXTENSIONS = set(['csv','xls'])

# Ports/Domains
MONGO_URL = 'localhost'
MONGO_PORT = 27017

# Mailgun
MAILGUN_DOMAIN = 'wsaf.ca'
FROM_EMAIL= 'Empties to WINN <emptiestowinn@wsaf.ca>'

# PHP
ETAP_WRAPPER_URL = 'http://www.bravoweb.ca/php/views.php'
