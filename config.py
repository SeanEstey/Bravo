import os
import logging
import pymongo

# TODO: Create a mongodb settings collection and webpage to manage these values

client = pymongo.MongoClient('localhost',27017)
db = client['wsf']

FROM_NUMBER= '+17804138846'
SMS_NUMBER='17808093927'
EMERGENCY_CONTACT='7808635715'
CALLER_ID= 'Winnifred Stewart Association'
BROKER_URI= 'amqp://'
PORT =5000
URL= 'http://23.239.21.165:5000'
AUTH_ID= 'MAMGFLNDVJMWE0NWU2MW'
AUTH_TOKEN= 'ZGFjOTEyN2RjMjBlZjU0YzY1NDg2MTc2ZjkyMzA5'
CPS= 1
MAX_ATTEMPTS= 3
REDIAL_DELAY = 60
EMAIL_USER = 'winnstew'
EMAIL_PW = 'batman()'
UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = set(['csv','xls'])
TEMPLATE_HEADERS = { 
  'etw_reminder': [
    'Name', 
    'Phone', 
    'Status', 
    'Next P/U Date', 
    'Office Notes'
  ],
  'etw_welcome': [
    'Name', 
    'Phone', 
    'Status', 
    'Next P/U Date', 
    'Office Notes'
  ],
  'special_msg': [
    'Name', 
    'Phone', 
    'Date'
  ],
  'gg_delivery': [
    'Name', 
    'Phone', 
    'Date', 
    'Price'
  ]
}

HEADERS_TO_MONGO = {
  'Name': 'name',
  'Phone': 'to',
  'Status': 'etw_status',
  'Next P/U Date': 'event_date',
  'Office Notes': 'office_notes',
}


def setLogger(logger, level, log_name):
    handler = logging.FileHandler(log_name)
    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(handler)
