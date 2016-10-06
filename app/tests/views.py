import unittest
import sys
import os
import pymongo

from app import app
from tasks import celery_app

import views # This should register the view functions for the app application

class TestViews(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.app = app.test_client()
        celery_app.conf.CELERY_ALWAYS_EAGER = True
        self.db = mongo_client['test']
        self.login(app.config['LOGIN_USER'], app.config['LOGIN_PW'])

    def tearDown(self):
        if hasattr(self, 'job_a'):
            self.db['jobs'].remove({'_id':self.job_a['_id']})
        if hasattr(self, 'job_b'):
            self.db['jobs'].remove({'_id':self.job_b['_id']})
        if hasattr(self, 'reminder'):
            self.db['reminders'].remove({'_id':self.reminder['_id']})

    def insertJobs(self):
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

    def login(self, username, password):
        return self.app.post('/login', data=dict(
          username=username,
          password=password
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def testGetSpeak(self):
        self.insertJobs()
        from reminders import bson_to_json
        r = self.app.post('/get_speak', data={
          'template': 'voice/etw_reminder.html',
          'reminder': bson_to_json(self.reminder)
        })
        self.assertTrue(type(r.data) == str)
        print r.data

    def testCallEvent_a(self):
        '''Test Case: rem_a call complete'''
        self.insertJobs()
        completed_call = {
            'To': self.reminder['voice']['to'],
            'CallSid': 'ABC123ABC123ABC123ABC123ABC123AB',
            'CallStatus': 'completed',
            'AnsweredBy': 'human',
            'CallDuration': 16
        }

        r = self.app.post('/reminders/call_event', data=completed_call)
        self.assertEquals(r._status_code, 200)

    def testEmailStatus_a(self):
        '''Case: gsheets delivered'''
        return True

    def testEmailStatus_b(self):
        '''Case: bounced email'''
        from data import email
        id = self.db['emails'].insert_one(email)
        r = self.app.post('/email/status', data={
        'event': 'bounced',
        'recipient': 'estesexyz123@gmail.com',
        'Message-Id': 'abc123'
        })
        self.assertEquals(r.status_code, 200)
        self.assertEquals(r.data, 'OK')

    def testRoot(self):
      r = self.app.get('/')
      self.assertEquals(r.status_code, 200)

    def testShowJobs(self):
      r = self.app.get('/')
      self.assertEquals(r.status_code, 200)

    def testViewLog(self):
      r = self.app.get('/log')
      self.assertEquals(r.status_code, 200)

    def testNewJob(self):
      r = self.app.get('/reminders/new')
      self.assertEquals(r.status_code, 200)

    def testViewJob(self):
      self.insertJobs()
      job_id = str(self.job_a['_id'])
      r = self.app.get('/reminders/' + job_id)
      self.assertEquals(r.status_code, 200)

    def testSendEmail(self):
      data = '{"data": {"from": "", "status": "Active", "next_pickup": "Monday, June 20", "office_notes": "", "type": "pickup", "account": {"name": "Test Res", "email": "estese@gmail.com"}}, "recipient": "estese@gmail.com", "template": "email/etw_reminder.html", "subject": "Your upcoming Empties to Winn event"}'
      self.insertJobs()
      r = self.app.post('/email/send', data=data, headers={"content-type": "application/json"})
      self.assertEquals(r.status_code, 200)

    def test_show_calls(self):
      self.insertJobs()
      r = self.app.get('/jobs' + str(self.job_id))
      self.assertEquals(r.status_code, 200)

    def test_schedule_jobs(self):
      r = self.app.get('/new')
      #self.assertEquals(r.status_code, 200)

    def test_get_speak_etw_dropoff(self):
        self.insertJobs()
        self.msg['etw_status'] = 'Dropoff'
        #speak = bravo.get_speak(self.job_a, self.msg)
        #self.assertIsInstance(speak, str)

    def test_show_calls_view(self):
        self.insertJobs()
        #r = self.app.get('/jobs/'+str(self.job_id))
        #self.assertEqual(r.status_code, 200)

if __name__ == '__main__':
    mongo_client = pymongo.MongoClient(app.config['MONGO_URL'],app.config['MONGO_PORT'])
    views.db = mongo_client['test']
    views.reminders.db = mongo_client['test']

    import logging

    # Modify loggers to redirect to tests.log before getting client
    log_formatter = logging.Formatter('[%(asctime)s %(name)s] %(message)s','%m-%d %H:%M')
    test_log_handler = logging.FileHandler(app.config['LOG_PATH'] + 'tests.log')
    test_log_handler.setLevel(logging.DEBUG)
    test_log_handler.setFormatter(log_formatter)

    app.logger.handlers = []
    app.logger.addHandler(test_log_handler)
    app.logger.setLevel(logging.DEBUG)

    from app.main import auth
    auth.logger = logging.getLogger(__name__)
    auth.logger.addHandler(test_log_handler)
    auth.logger.setLevel(logging.DEBUG)

    views.app.logger.handlers = []
    views.app.logger.addHandler(test_log_handler)
    views.app.logger.setLevel(logging.DEBUG)

    #views.routing.logger = logging.getLogger(views.__name__)
    #views.receipts.logger = logging.getLogger(views.__name__)
    #views.scheduler.logger = logging.getLogger(views.__name__)
    #views.gsheets.logger = logging.getLogger(views.__name__)
    #views.log.logger = logging.getLogger(views.__name__)

    from datetime import datetime
    now = datetime.now()
    app.logger.info(now.strftime('\n[%m-%d %H:%M] *** START VIEWS UNIT TEST ***\n'))

    unittest.main()
