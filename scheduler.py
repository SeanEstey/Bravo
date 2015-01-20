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

@celery_app.task
def run_scheduler():
  if not systems_check():
    return False 

  pending_jobs = db['jobs'].find({'status': 'pending'})
  logger.info('Scheduler: ' + str(pending_jobs.count()) + ' pending jobs:')

  job_num = 1
  for job in pending_jobs:
    if datetime.now() > job['fire_dtime']:
      logger.info('Starting job %s' % str(job['_id']))
      requests.get('http://localhost:5000/request/execute/schedule')
      execute_job.delay(job['_id'])
    else:
      next_job_delay = job['fire_dtime'] - datetime.now()
      logger.info(str(job_num) + '): ' + job['name'] + ' starts in: ' + str(next_job_delay))
    job_num += 1
  return True


