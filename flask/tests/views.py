import unittest
import sys
import os
import pymongo

os.chdir('/root/bravo_dev/Bravo/flask')
sys.path.insert(0, '/root/bravo_dev/Bravo/flask')

from config import *
from app import flask_app, celery_app

import views # This should register the view functions for the flask_app application

class TestViews(unittest.TestCase):
    def setUp(self):
        flask_app.testing = True
        self.app = flask_app.test_client()
        celery_app.conf.CELERY_ALWAYS_EAGER = True

        self.db = mongo_client['test']
        self.login(LOGIN_USER, LOGIN_PW)

        from data import job, reminder

        job_a_id = self.db['jobs'].insert_one(job).inserted_id
        del job['_id'] # insert_one modifies job and adds _id
        job['name'] = 'job_b'
        job_b_id = self.db['jobs'].insert_one(job).inserted_id
        self.job_a = self.db['jobs'].find_one({'_id':job_a_id})
        self.job_b = self.db['jobs'].find_one({'_id':job_b_id})
        reminder['job_id'] = self.job_a['_id']
        id = self.db['reminders'].insert_one(reminder).inserted_id
        self.reminder = self.db['reminders'].find_one({'_id':id})

    def tearDown(self):
        self.db['jobs'].remove({'_id':self.job_a['_id']})
        self.db['jobs'].remove({'_id':self.job_b['_id']})
        self.db['reminders'].remove({'_id':self.reminder['_id']})

        # Remove job record created by setUp
        #res = self.db['emails'].remove({'_id':self.test_email_id})
        #self.assertEquals(res['n'], 1)
        return True

    def login(self, username, password):
        return self.app.post('/login', data=dict(
          username=username,
          password=password
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_get_speak(self):
        from reminders import bson_to_json
        r = self.app.post('/get_speak', data={
          'template': 'voice/etw_reminder.html',
          'reminder': bson_to_json(self.reminder)
        })
        self.assertTrue(type(r.data) == str)
        print r.data

    """
    def test_call_event_a(self):
        '''Test Case: rem_a call complete'''
        completed_call = {
        'To': self.reminder['voice']['to'],
        'CallSid': 'ABC123ABC123ABC123ABC123ABC123AB',
        'CallStatus': 'completed',
        'AnsweredBy': 'human',
        'CallDuration': 16
        }

        r = self.app.post('/reminders/call_event', data=completed_call)
        self.assertEquals(r._status_code, 200)
        #logger.info(self.db['reminders'].find_one({'voice.sid':completed_call['CallSid']}))

  def test_email_status_gsheets_delivered(self):
      r = self.app.post('/email/status', data={
        'event': 'delivered',
        'recipient': 'estese@gmail.com',
        'Message-Id': 'abc123'
      })
      self.assertEquals(r.status_code, 200)
      self.assertEquals(r.data, 'OK')

  def test_email_status_gsheets_bounced(self):
      r = self.app.post('/email/status', data={
        'event': 'bounced',
        'recipient': 'estesexyz123@gmail.com',
        'Message-Id': 'abc123'
      })
      self.assertEquals(r.status_code, 200)
      self.assertEquals(r.data, 'OK')

  def test_email_status_reminder_delivered(self):
      r = self.app.post('/email/status', data={
        'event': 'bounced',
        'recipient': 'estesexyz123@gmail.com',
        'Message-Id': 'abc123'
      })
      self.assertEquals(r.status_code, 200)
      self.assertEquals(r.data, 'OK')

  def test_root(self):
      r = self.app.get('/')
      self.assertEquals(r.status_code, 200)

  def test_show_jobs(self):
      r = self.app.get('/jobs')
      self.assertEquals(r.status_code, 200)

  def test_show_calls(self):
      r = self.app.get('/jobs' + str(self.job_id))
      self.assertEquals(r.status_code, 200)

  def test_schedule_jobs(self):
      r = self.app.get('/new')
      self.assertEquals(r.status_code, 200)

    def test_schedule_jobs_view(self):
        self.assertEqual(requests.get(PUB_URL+'/new').status_code, 200)

    def test_root_view(self):
        self.assertEquals(requests.get(PUB_URL).status_code, 200)

    def test_get_speak_etw_dropoff(self):
        self.msg['etw_status'] = 'Dropoff'
        speak = bravo.get_speak(self.job_a, self.msg)
        self.assertIsInstance(speak, str)

    def test_show_jobs_view(self):
        self.assertEqual(requests.get(PUB_URL+'/jobs').status_code, 200)

    def test_show_calls_view(self):
        uri = PUB_URL + '/jobs/' + str(self.job_id)
        self.assertEqual(requests.get(uri).status_code, 200)
  """

if __name__ == '__main__':
    mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)

    # Modify loggers to redirect to tests.log before getting client
    test_log_handler = logging.FileHandler(LOG_PATH + 'tests.log')
    views.logger.handlers = []
    views.logger = logging.getLogger(views.__name__)
    #views.logger.setFormatter(log_formatter)
    views.logger.addHandler(test_log_handler)
    views.logger.setLevel(logging.DEBUG)
    views.auth.logger = logging.getLogger(views.__name__)
    views.reminders.logger = logging.getLogger(views.__name__)
    views.routing.logger = logging.getLogger(views.__name__)
    views.receipts.logger = logging.getLogger(views.__name__)
    views.scheduler.logger = logging.getLogger(views.__name__)
    views.gsheets.logger = logging.getLogger(views.__name__)
    views.log.logger = logging.getLogger(views.__name__)

    from datetime import datetime
    now = datetime.now()
    views.logger.info(now.strftime('\n[%m-%d %H:%M] *** START VIEWS UNIT TEST ***\n'))

    unittest.main()
