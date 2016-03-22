import unittest
import requests
import json
import sys
import os
import time
import twilio
import pymongo
import json
import datetime
from dateutil.parser import parse
from werkzeug.datastructures import MultiDict
import xml.dom.minidom
os.chdir('/home/sean/Bravo/flask')
sys.path.insert(0, '/home/sean/Bravo/flask')
#os.chdir('/root/bravo_experimental/Bravo/flask')
#sys.path.insert(0, '/root/bravo_experimental/Bravo/flask')

from config import *
import views
import gsheets
import receipts
import views
from app import logger, flask_app, celery_app

class BravoTestCase(unittest.TestCase):

  def setUp(self):
      flask_app.config['TESTING'] = True
      self.app = flask_app.test_client()
      celery_app.conf.CELERY_ALWAYS_EAGER = True

      mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
      self.db = mongo_client[DB_NAME]
      self.job_id = self.db['reminder_jobs'].insert(self.job_document)
      self.job = self.db['reminder_jobs'].find_one({'_id':self.job_id})
      self.login('seane@wsaf.ca', 'wsf')

      self.test_email_id = db['emails'].insert({
        'mid': 'abc123',
        'status': 'queued',
        'on_status_update': {
          'sheet_name': 'Route Importer',
          'worksheet_name': 'Signups',
          'row': 2,
          'upload_status': 'Success'
        }
      })

  # Remove job record created by setUp
  def tearDown(self):
      res = self.db['emails'].remove({'_id':self.test_email_id})
      self.assertEquals(res['n'], 1)

  def login(self, username, password):
      return self.app.post('/login', data=dict(
          username=username,
          password=password
      ), follow_redirects=True)

  def logout(self):
      return self.app.get('/logout', follow_redirects=True)

  def test_email_status(self):
      r = self.app.post('/email/status', data={
        'event': 'delivered',
        'recipient': 'estese@gmail.com',
        'Message-Id': 'abc123'
      })
      self.assertEquals(r.status_code, 200)
  
  def test_root(self):
      r = self.app.get('/')
      self.assertEquals(r.status_code, 200)
  
  def test_show_jobs(self):
      r = self.app.get('/jobs')
      self.assertEquals(r.status_code, 200)

  def test_show_calls(self):
      r = self.app.get('/jobs' + str(self.job_id)
      self.assertEquals(r.status_code, 200)

  def test_schedule_jobs(self):
      r = self.app.get('/new')
      self.assertEquals(r.status_code, 200)

if __name__ == '__main__':
    logger.info('********** begin views.py unittest **********')
    unittest.main()
