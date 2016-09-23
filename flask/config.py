from auth_keys import *

# App
DEBUG = False # Uses Werkzeug dev server when True, otherwise gevent (wsgi, threaded)
AGENCIES = ['vec', 'wsf']
DB = 'bravo' # Mongo Database
MONGO_URL = 'localhost'
MONGO_PORT = 27017
LOCAL_PORT = 8000
LOCAL_URL = 'http://localhost:8000'
PUB_URL = 'http://bravoweb.ca'
TITLE = 'Bravo'
LOG_PATH = '/var/www/bravo/logs/'
LOG_LINES = 200

# Gsheets.py module
GSHEET_NAME = 'Bravo Sheets'

# Universal app settings
JOB_TIME_LIMIT = 3000
EMERGENCY_CONTACT='7808635715'
MAX_CALL_ATTEMPTS= 2
REDIAL_DELAY = 300
UPLOAD_FOLDER = '/tmp'
JOBS_PER_PAGE = 10
ALLOWED_EXTENSIONS = set(['csv','xls'])

# PHP
ETAP_WRAPPER_URL = 'http://www.bravoweb.ca/php/views.php'
ETAPESTRY_ENDPOINT = 'https://sna.etapestry.com/v3messaging/service?WSDL'
