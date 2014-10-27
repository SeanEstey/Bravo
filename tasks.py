from celery import Celery
from celery.utils.log import get_task_logger
from config import *
from bson.objectid import ObjectId
import plivo
import pymongo
import urllib2
import csv
import logging
import time
import json
import monitor

celery = Celery('tasks', cache='amqp', broker=BROKER_URI)
logger = get_task_logger(__name__)
setLogger(logger, logging.INFO, 'log.log')

#-------------------------------------------------------------------
@celery.task
def monitor_bulk_call(job_id):
    logger.log('Monitoring job %s' % job_id)
    '''
    Monitor calls via mongoDB:
    Loop through all records with job_id
        Redial busy numbers/no answers (up to MaxAttempts), 
        Check if job is complete
            If complete, email report to emptiestowinn@wsaf.ca
    Sleep(5 minutes)
    '''

#-------------------------------------------------------------------
@celery.task
def fire_bulk_call(job_id):
    # job_id is the default _id field created for each call_jobs document by mongo
    logger.info('Starting job %s' % job_id)

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    job = db['call_jobs'].find_one({'_id':ObjectId(job_id)})

    to = ''
    csv_data = urllib2.urlopen(job['csv_url'])
    reader = csv.reader(csv_data)
    cps = int(job['cps'])
  
    # CSV format: NAME,PICKUP_DATE,PHONE
    for row in reader:
      response = monitor.dial(row[2])
      monitor.call_to_db(response, job_id, csv_row=row)

#-------------------------------------------------------------------
@celery.task
def validate_message(id):
    '''fire the validation and thus fire the calls'''
    print "Validating: ", id

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    data = db['calls'].find_one({'request_id':id})

    print "Got data:", data['from_number']

    params = {
        'from' : FROM_NUMBER,
        'caller_name': CALLER_ID,
        'to'   : data['from_number'],
        'answer_url' : URL+'/verify/'+id
    }

    print "Params are: ", params

    p = plivo.RestAPI(data['auth_id'],data['auth_token'])
    resp = p.make_call(params)
    print "Fired: ", resp
