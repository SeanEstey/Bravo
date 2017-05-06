from datetime import timedelta

# Flask
#LOGGER_NAME = 'flask'
TEMPLATES_AUTO_RELOAD = True
SESSION_COLLECTION = 'sessions'
PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
SECRET_KEY = 'secret'

# App
TITLE = 'Bravo'
SSL_CERT_PATH = '/etc/nginx/bravoweb.ca.chained.crt'
LOG_PATH = '/root/bravo/logs/'
MONGO_URL = 'localhost'
MONGO_PORT = 27017
LOCAL_PORT = 8000
LOCAL_URL = 'http://localhost:%s' % LOCAL_PORT
PUB_PORT = 80
DB = 'bravo'
APP_ROOT_LOGGER_NAME = 'app'
CELERY_ROOT_LOGGER_NAME = 'app'

# Other
GSHEET_NAME = 'Bravo Sheets'
ENV_VARS = [
    'BRV_SANDBOX',
    'BRV_BEAT',
    'BRV_HTTP_HOST',
    'BRV_TEST']
BLOCK_SIZES = {
  'RES': {
    'MED': 60,
    'LRG': 75,
    'MAX': 90,
  },
  'BUS': {
    'MED': 20,
    'LRG': 23,
    'MAX': 25
  }
}
BOOKING = {
    'MAX_BLOCK_RADIUS': 10,
    'MAX_SCHEDULE_DAYS_WAIT': 14,
    'SEARCH_WEEKS': 16
}
