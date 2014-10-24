from celery import Celery
from config import *
from bson.objectid import ObjectId
import plivo
import pymongo
import urllib2
import csv
import logging
import time
import json

celery = Celery('tasks', cache='amqp', broker=BROKER_URI)

#-------------------------------------------------------------------
@celery.task
def fire_bulk_call(job_id):
    # job_id is the default _id field created for each call_jobs document by mongo
    print "Bulk call entry point for :", job_id

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    job = db['call_jobs'].find_one({'_id':ObjectId(job_id)})
    print "Job got:", job

    to = ''
    csv_data = urllib2.urlopen(job['csv_url'])
    reader = csv.reader(csv_data)
    cps = int(job['cps'])
    server = plivo.RestAPI(job['auth_id'], job['auth_token'])
  
    # CSV format: NAME,PICKUP_DATE,PHONE
    for row in reader:
      params = { 
        'from' : FROM_NUMBER,
        'caller_name': CALLER_ID,
        'to' : row[2],
        'answer_url' : URL+'/call/answer',
        'answer_method': 'POST',
        'hangup_url': URL+'/call/hangup',
        'hangup_method': 'POST',
        'machine_detection': 'true',
        'machine_detection_url': URL+'/call/machine',
        'name': row[0],
        'date': row[1],
        'ring_url' : COUNTER_URL
      }

      print 'Making Bulk Call:',params
      resp = server.make_call(params)
      print resp
      call = {
          '_id': resp[1]['request_uuid'],
          'job_id': job_id,
          'to': params['to'],
          'status': resp[1]['message'],
          'name': params['name'],
          'event_date': params['date']
      }
      db['calls'].insert(call)

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
