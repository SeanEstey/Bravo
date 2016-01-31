from config import *
from server_settings import *
from reminders import dial
from celery import Celery
from celery.signals import worker_process_init, task_prerun
import time
import os
from dateutil.parser import parse
from datetime import datetime,date
from bson.objectid import ObjectId
import pymongo
import twilio
from twilio import twiml
import logging
import requests
import json
import dateutil
import httplib2
from oauth2client.client import SignedJwtAssertionCredentials 
from apiclient.discovery import build
import gspread

logger = logging.getLogger(__name__)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(LOG_LEVEL)
handler.setFormatter(formatter)
logger.setLevel(LOG_LEVEL)
logger.addHandler(handler)
celery_app = Celery('tasks')
celery_app.config_from_object('config')
mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT, connect=False)
db = mongo_client[DB_NAME]

@celery_app.task
def no_pickup_etapestry(url, params):
  r = requests.get(url, params=params)
  
  if r.status_code != 200:
    logger.error('etap script "%s" failed. status_code:%i', url, r.status_code)
    return r.status_code
  
  logger.info('No pickup for account %s', params['account'])

  return r.status_code



