import unittest
import json
import sys
import os
import time
import pymongo
import codecs
from datetime import datetime, timedelta
from dateutil.parser import parse
from werkzeug.datastructures import MultiDict
import xml.dom.minidom
from bson.objectid import ObjectId

#os.chdir('/root/bravo_dev/Bravo/flask')
#sys.path.insert(0, '/root/bravo_dev/Bravo/flask')

from app import app
#from tasks import celery_app
#import reminders
#import views

class TestReminders(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        celery_app.conf.CELERY_ALWAYS_EAGER = True
        self.db = mongo_client['test']
        self.login('sestey@vecova.ca', 'vec')

    def tearDown(self):
        if hasattr(self, 'job_a'):
            self.db['jobs'].remove({'_id':self.job_a['_id']})
            self.db['reminders'].remove({'job_id':self.job_a['_id']})
        if hasattr(self, 'job_b'):
            self.db['jobs'].remove({'_id':self.job_b['_id']})
            self.db['reminders'].remove({'job_id':self.job_b['_id']})

    def insertJobsAndReminder(self):
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

    def update_db(self, collection, a_id, a_set):
        self.db[collection].update_one({'_id':a_id},{'$set':a_set})

    def login(self, username, password):
        return self.client.post('/login', data=dict(
          username=username,
          password=password
        ), follow_redirects=True)

    """
    def test_dial_a(self):
        call = reminders.dial('7808635715')
        self.assertEquals(call.status, 'queued')

    def test_get_answer_xml_template_a(self):
        '''Test Case: human answers'''
        self.insertJobsAndReminder()
        reminders.get_answer_xml_template({
            'CallSid': self.reminder['voice']['sid'],
            'To': self.reminder['voice']['to'],
            'CallStatus': 'in-progress',
            'AnsweredBy': 'human'
        })

    def test_get_answer_xml_template_b(self):
        '''Test Case: answering machine'''
        self.insertJobsAndReminder()
        reminders.get_answer_xml_template({
            'CallSid': self.reminder['voice']['sid'],
            'To': self.reminder['voice']['to'],
            'CallStatus': 'in-progress',
            'AnsweredBy': 'machine'
        })

    def test_get_resp_xml_template_b(self):
        '''Test Case: answering machine'''
        self.insertJobsAndReminder()
        reminders.get_answer_xml_template({
            'CallSid': self.reminder['voice']['sid'],
            'Digits': 1,
            'To': self.reminder['voice']['to'],
            'CallStatus': 'in-progress',
            'AnsweredBy': 'machine'
        })

    def test_monitor_pending_jobs_a(self):
        '''Test Case: job_a is pending'''
        self.insertJobsAndReminder()
        self.update_db('jobs', self.job_a['_id'],{'voice.fire_at':datetime.now()+timedelta(hours=1)})
        self.update_db('jobs', self.job_b['_id'],{'voice.fire_at':datetime.now()+timedelta(hours=1)})
        status = reminders.monitor_pending_jobs()
        self.assertTrue(status[self.job_a['_id']] == 'pending')

    def test_monitor_pending_jobs_b(self):
        '''Test Case: job_a ready but job_b in progress'''
        self.insertJobsAndReminder()
        self.update_db('jobs', self.job_b['_id'],{'status':'in-progress'})
        self.update_db('jobs', self.job_a['_id'],{'status':'pending','voice.fire_at':datetime.now()-timedelta(hours=1)})
        status = reminders.monitor_pending_jobs()
        self.assertTrue(status[self.job_a['_id']] == 'waiting')

    def test_monitor_pending_jobs_c(self):
        '''Test Case: starting new job'''
        self.insertJobsAndReminder()
        self.update_db('jobs', self.job_a['_id'],{'voice.fire_at':datetime.now()-timedelta(hours=1)})
        self.update_db('jobs', self.job_b['_id'],{'voice.fire_at':datetime.now()+timedelta(hours=1)})
        status = reminders.monitor_pending_jobs()
        self.assertTrue(status[self.job_a['_id']] == 'in-progress')

    def test_monitor_active_jobs_a(self):
        '''Test Case: job_a hung (went over time limit)'''
        self.insertJobsAndReminder()
        self.update_db('jobs', self.job_a['_id'],{'status':'in-progress','voice.started_at':datetime.now()-timedelta(hours=1)})
        self.update_db('jobs', self.job_b['_id'],{'voice.fire_at':datetime.now()+timedelta(hours=1)})
        status = reminders.monitor_active_jobs()
        self.assertTrue(status[self.job_a['_id']] == 'failed')

    def test_monitor_active_jobs_b(self):
        '''Test Case: job_a is active'''
        self.insertJobsAndReminder()
        self.update_db('jobs',
        self.job_a['_id'],{'status':'in-progress','voice.fire_at':datetime.now()-timedelta(hours=1),'voice.started_at':datetime.now()})
        self.update_db('jobs', self.job_b['_id'],{'voice.fire_at':datetime.now()+timedelta(hours=1)})
        status = reminders.monitor_active_jobs()
        self.assertTrue(status[self.job_a['_id']] == 'in-progress')

    def test_monitor_active_jobs_c(self):
        '''Test Case: job_a has completed.'''
        self.insertJobsAndReminder()
        self.update_db('jobs',self.job_a['_id'],
            {'status':'in-progress','voice.started_at':datetime.now(),'voice.fire_at':datetime.now()-timedelta(hours=1)})
        self.update_db('reminders',self.reminder['_id'],{'voice.status':'completed','voice.attempts':1})
        status = reminders.monitor_active_jobs()
        self.assertTrue(status[self.job_a['_id']] == 'completed')

    def test_monitor_active_jobs_d(self):
        '''Test Case: job_a is incomplete. redialing.'''
        '''self.insertJobsAndReminder()
        self.update_db('jobs',self.job_a['_id'],
            {'status':'in-progress','voice.started_at':datetime.now(),'voice.fire_at':datetime.now()-timedelta(hours=1)})
        self.update_db('reminders',self.reminder['_id'],{'voice.status':'busy','voice.attempts':1})
        self.update_db('jobs', self.job_b['_id'],{'voice.fire_at':datetime.now()+timedelta(hours=1)})
        status = reminders.monitor_active_jobs()
        self.assertTrue(str(status[self.job_a['_id']]) == 'redialing')'''

    def test_parse_csv_a(self):
        '''Test Case: Success'''
        #filepath = '/tmp/ETW_Res_5E.csv'
        #with codecs.open(filepath, 'r', 'utf-8-sig') as f:
        #  self.assertIsNotNone(parse_csv(f, TEMPLATE_HEADERS['etw_reminder']))
        return True

    def test_parse_csv_b(self):
        '''Test Case: headers don't match schema'''

    def test_parse_csv_c(self):
        '''Test Case: data format doesn't schema'''

    def test_csv_line_to_db_a(self):
        '''self.insertJobsAndReminder()
        line = [57515,'Sean','(780) 863-5715','estese@gmail.com','R1R','Dropoff','12/3/2014','']
        errors = []
        self.assertIsNotNone(reminders.csv_line_to_db(self.job_a['_id'],self.job_a['schema'],line, errors))
        '''

    def test_create_job(self):
        return True
    """

    def test_cancel_pickup(self):
        with self.client:
            self.login('sestey@vecova.ca', 'vec')
            reminders.logger.info(self.client.__dict__)
            self.insertJobsAndReminder()
            reminders.cancel_pickup(str(self.reminder['_id']))


if __name__ == '__main__':
    mongo_client = pymongo.MongoClient(app.config['MONGO_URL'], app.config['MONGO_PORT'])
    reminders.db = mongo_client['test']

    # Use test endpoints
    reminders.TWILIO_ACCOUNT_SID = app.config['TWILIO_TEST_ACCOUNT_SID']
    reminders.TWILIO_AUTH_ID = app.config['TWILIO_TEST_AUTH_ID']
    reminders.FROM_NUMBER = '+15005550006'
    INVALID_NUMBER = '+15005550001'
    UNROUTABLE_NUMBER = '+15005550002'

    import logging

    # Set logger to redirect to tests.log
    test_log_handler = logging.FileHandler(app.config['LOG_PATH'] + 'tests.log')
    reminders.logger.handlers = []
    reminders.logger = logging.getLogger(reminders.__name__)
    reminders.logger.addHandler(test_log_handler)
    reminders.logger.setLevel(logging.DEBUG)

    now = datetime.now()
    reminders.logger.info(now.strftime('\n[%m-%d %H:%M] *** STARTING REMINDERS UNIT TEST ***\n'))
    unittest.main()
