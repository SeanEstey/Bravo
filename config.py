from datetime import timedelta

SSL_CERT_PATH = '/etc/nginx/gd_bundle-g2-g1.crt'
TITLE = 'Bravo'
LOG_PATH = '/root/bravo/logs/'
LOG_LINES = 200
DB = 'bravo'
SESSION_COLLECTION = 'sessions'
PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
MONGO_URL = 'localhost'
MONGO_PORT = 27017
LOCAL_PORT = 8000
LOCAL_URL = 'http://localhost:%s' % LOCAL_PORT
PUB_PORT = 80
SECRET_KEY = 'secret'
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
