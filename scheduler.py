from config import *
from celery import Celery
from celery.utils.log import get_task_logger
import pymongo
import csv
import logging
import requests
import os

local_url = None
pub_url = None
logger = logging.getLogger(__name__)

celery = Celery('scheduler', broker=CELERY_BROKER_URL)
celery.config_from_object('config')

import requests

def restart_server():
  logger.info('Attempting server restart...')
  os.system('python server.py &')
  time.sleep(5)
  if is_server_online() == False:
    #sms(EMERGENCY_CONTACT, 'Bravo server offline! Cannot execute job!')
    return False

  logger.info('Successfully restarted. Resuming job...')
  return True

def is_server_online():
  try:
    response = requests.get(local_url)
    if response.status_code == 200:
      return True
    else:
      return False
  except Exception, e:
    return False

def systems_check():
  #if not is_celery_worker():
    #if not restart_celery():
  #    return False 
  if not is_server_online():
    return False
  #  if not restart_server():
  #    return False 
  if not is_mongodb_available():
    if not reconnect_mongodb():
      return False

  return True



