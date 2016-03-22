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

      self.job_document = {
        'template': 'etw_reminder',
        'status': 'pending',
        'name': 'test',
        'fire_dtime': datetime.datetime(2014, 12, 31),
        'num_calls': 1
      }

      mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
      self.db = mongo_client[DB_NAME]
      self.job_id = self.db['reminder_jobs'].insert(self.job_document)
      self.job = self.db['reminder_jobs'].find_one({'_id':self.job_id})
      self.login('seane@wsaf.ca', 'wsf')

      self.msg_document = {
        'job_id': self.job_id,
        'name': 'Test Res',
        'account_id': '57515',
        'event_date': '',
        'call_status': 'pending',
        'attempts': 0,
        'imported': {
          'event_date': parse('december 31, 2014'),
          'to': '780-863-5715',
          'name': 'NIS',
          'status': 'Active',
          'office_notes': ''
        }
      }

      self.msg_id = self.db['reminder_msgs'].insert(self.msg_document)
      self.msg = self.db['reminder_msgs'].find_one({'_id':self.msg_id})

  # Remove job record created by setUp
  def tearDown(self):
      res = self.db['reminder_jobs'].remove({'_id':self.job_id})
      self.assertEquals(res['n'], 1)
      res = self.db['reminder_msgs'].remove({'_id':self.msg_id})
      self.assertEquals(res['n'], 1)

  def login(self, username, password):
      return self.app.post('/login', data=dict(
          username=username,
          password=password
      ), follow_redirects=True)

  def logout(self):
      return self.app.get('/logout', follow_redirects=True)

  def test_show_jobs_view(self):
      self.assertEqual(requests.get(PUB_URL+'/jobs').status_code, 200)

  def test_show_calls_view(self):
      uri = PUB_URL + '/jobs/' + str(self.job_id)
      self.assertEqual(requests.get(uri).status_code, 200)

  def test_schedule_jobs_view(self):
      self.assertEqual(requests.get(PUB_URL+'/new').status_code, 200)

  def test_root_view(self):
      self.assertEquals(requests.get(PUB_URL).status_code, 200)

if __name__ == '__main__':
    logger.info('********** begin views.py unittest **********')
    unittest.main()
