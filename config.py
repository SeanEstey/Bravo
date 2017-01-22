from datetime import timedelta

TITLE = 'Bravo'
LOG_PATH = '/var/www/bravo/logs/'
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
    'BRAVO_SANDBOX_MODE',
    'BRAVO_CELERY_BEAT',
    'BRAVO_HTTP_HOST',
    'BRAVO_TEST_SERVER']
