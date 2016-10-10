
# Uses Werkzeug dev server when True, otherwise gevent (wsgi, threaded)
DEBUG = False
DB = 'bravo'
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

# PHP
ETAP_WRAPPER_URL = 'http://www.bravoweb.ca/php/views.php'
ETAPESTRY_ENDPOINT = 'https://sna.etapestry.com/v3messaging/service?WSDL'

SECRET_KEY = 'secret'
