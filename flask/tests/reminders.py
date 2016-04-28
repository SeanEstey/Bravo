import unittest
import json
import sys
import os
import time
import pymongo
import codecs
from datetime import datetime
from dateutil.parser import parse
from werkzeug.datastructures import MultiDict
import xml.dom.minidom

os.chdir('/root/bravo_dev/Bravo/flask')
sys.path.insert(0, '/root/bravo_dev/Bravo/flask')

from app import flask_app, celery_app, log_handler
from config import *
import reminders
import views

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)

class BravoTestCase(unittest.TestCase):
    def setUp(self):
        flask_app.config['TESTING'] = True
        self.app = flask_app.test_client()
        celery_app.conf.CELERY_ALWAYS_EAGER = True
        mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
        self.db = mongo_client['test']
        self.login(LOGIN_USER, LOGIN_PW)

        reminders.TWILIO_ACCOUNT_SID = TWILIO_TEST_ACCOUNT_SID
        reminders.TWILIO_AUTH_ID = TWILIO_TEST_AUTH_ID
        reminders.FROM_NUMBER = '+15005550006'

        with open('templates/reminder_schemas.json') as json_file:
          schemas = json.load(json_file)

        job = {
          'schema': schemas['etw'],
          'status': 'pending',
          'name': 'job_a',
          'fire_calls_dtime': parse('Dec 31, 2015'),
          'num_calls': 1
        }

        job_a_id = self.db['jobs'].insert_one(job).inserted_id
        del job['_id']
        job['name'] = 'job_b'
        job_b_id = self.db['jobs'].insert_one(job).inserted_id

        self.job_a = self.db['jobs'].find_one({'_id':job_a_id})
        self.job_b = self.db['jobs'].find_one({'_id':job_b_id})


        reminder = {
            'job_id': self.job_a['_id'],
            'name': 'Test Res',
            'account_id': '57515',
            'event_date': parse('December 31, 2014'),
            'call': {
              'sid': 'ABC123ABC123ABC123ABC123ABC123AB',
              'status': 'pending',
              'attempts': 0,
              'to': '780-863-5715',
            },
            'email': {
              'status':  'pending',
              'recipient': 'estese@gmail.com'
            },
            'custom': {
              'next_pickup': parse('June 21, 2016'),
              'type': 'pickup',
              'status': 'Active',
              'office_notes': ''
            }
        }

        id = self.db['reminders'].insert_one(reminder).inserted_id
        self.reminder = self.db['reminders'].find_one({'_id':id})

    def tearDown(self):
        res = self.db['jobs'].remove({'_id':self.job_a['_id']})
        res = self.db['jobs'].remove({'_id':self.job_b['_id']})
        res = self.db['reminders'].remove({'_id':self.reminder['_id']})

    def update_db(self, collection, a_id, a_set):
        self.db[collection].update_one({'_id':a_id},{'$set':a_set})

    def login(self, username, password):
        return self.app.post('/login', data=dict(
          username=username,
          password=password
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_dial_a(self):
        call = reminders.dial('7808635715')
        self.assertEquals(call.status, 'queued')

    def test_get_answer_xml_template_a(self):
        '''Code Path: human answers'''
        reminders.get_answer_xml_template({
            'CallSid': self.reminder['call']['sid'],
            'To': self.reminder['call']['to'],
            'CallStatus': 'in-progress',
            'AnsweredBy': 'human'
        })

    def test_get_answer_xml_template_b(self):
        '''Code Path: answering machine'''
        reminders.get_answer_xml_template({
            'CallSid': self.reminder['call']['sid'],
            'To': self.reminder['call']['to'],
            'CallStatus': 'in-progress',
            'AnsweredBy': 'machine'
        })

    def test_get_speak(self):
        r = self.app.post('/get_speak', data={
          'template': 'speak/etw_reminder.html',
          'reminder': reminders.bson_to_json(self.reminder)
        })
        self.assertTrue(type(r.data) == str)
        logger.info(r.data)

    def test_call_event_a(self):
        '''Code Path: rem_a call complete'''
        completed_call = {
        'To': self.reminder['call']['to'],
        'CallSid': 'ABC123ABC123ABC123ABC123ABC123AB',
        'CallStatus': 'completed',
        'AnsweredBy': 'human',
        'CallDuration': 16
        }

        r = self.app.post('/reminders/call_event', data=completed_call)
        self.assertEquals(r._status_code, 200)
        #logger.info(self.db['reminders'].find_one({'call.sid':completed_call['CallSid']}))

    def test_send_calls(self):
        r = reminders.send_calls.apply_async(args=(str(self.job_id),),queue=DB_NAME)
        self.assertTrue(type(r.result), int)

    def test_monitor_pending_jobs_a(self):
        '''Code Path: job_a is pending'''
        self.update_db('jobs', self.job_a['_id'],{'fire_calls_dtime':datetime.now()+timedelta(hours=1)})
        self.update_db('jobs', self.job_b['_id'],{'fire_calls_dtime':datetime.now()+timedelta(hours=1)})
        n = reminders.monitor_jobs.apply_async(queue=DB_NAME)

    def test_monitor_pending_jobs_b(self):
        '''Code Path: job_a ready but job_b in progress'''
        self.update_db('jobs', self.job_b['_id'],{'status':'in-proress'})
        self.update_db('jobs', self.job_a['_id'],{'fire_calls_dtime':datetime.now()-timedelta(hours=1)})
        n = reminders.monitor_jobs.apply_async(queue=DB_NAME)

    def test_monitor_pending_jobs_c(self):
        '''Code Path: starting new job'''
        self.update_db('jobs', self.job_a['_id'],{'fire_calls_dtime':datetime.now()-timedelta(hours=1)})
        self.update_db('jobs', self.job_b['_id'],{'fire_calls_dtime':datetime.now()+timedelta(hours=1)})
        n = reminders.monitor_jobs.apply_async(queue=DB_NAME)

    def test_monitor_active_jobs_a(self):
        '''Code Path: job_a hung (went over time limit)'''
        self.update_db('jobs', self.job_a['_id'],{'fire_calls_dtime':datetime.now()-timedelta(hours=1)})
        self.update_db('jobs', self.job_b['_id'],{'fire_calls_dtime':datetime.now()+timedelta(hours=1)})
        n = reminders.monitor_jobs.apply_async(queue=DB_NAME)

    def test_monitor_active_jobs_b(self):
        '''Code Path: job_a is active'''
        self.update_db('jobs', self.job_a['_id'],{'fire_calls_dtime':datetime.now()-timedelta(hours=1)})
        self.update_db('jobs', self.job_b['_id'],{'fire_calls_dtime':datetime.now()+timedelta(hours=1)})
        n = reminders.monitor_jobs.apply_async(queue=DB_NAME)

    def test_monitor_active_jobs_c(self):
        '''Code Path: job_a has completed.'''
        self.update_db('jobs',self.job_a['_id'],
            {'status':'in-progress','started_dtime':datetime.now(),'fire_calls_dtime':datetime.now()-timedelta(hours=1)})
        self.update_db('reminders',self.reminder['_id'],{'call.status':'completed','call.attempts':1})
        reminders.monitor_active_jobs()

    def test_monitor_active_jobs_d(self):
        '''Code Path: job_a is incomplete. redialing.'''
        self.update_db('jobs',self.job_a['_id'],
            {'status':'in-progress','started_dtime':datetime.now(),'fire_calls_dtime':datetime.now()-timedelta(hours=1)})
        self.update_db('reminders',self.reminder['_id'],{'call.status':'busy','call.attempts':1})
        self.update_db('jobs', self.job_b['_id'],{'fire_calls_dtime':datetime.now()+timedelta(hours=1)})
        self.assertEquals(reminders.monitor_active_jobs(), 1)

    def test_send_calls(self):
        r = reminders.send_calls.apply_async(args=(str(self.job_a['_id']),),queue=DB_NAME)
        self.assertTrue(type(r.result), int)

    def test_parse_csv_a(self):
        '''Code Path: Success'''
        #filepath = '/tmp/ETW_Res_5E.csv'
        #with codecs.open(filepath, 'r', 'utf-8-sig') as f:
        #  self.assertIsNotNone(parse_csv(f, TEMPLATE_HEADERS['etw_reminder']))
        return True

    def test_parse_csv_b(self):
        '''Code Path: headers don't match schema'''

    def test_parse_csv_c(self):
        '''Code Path: data format doesn't schema'''

    def test_csv_line_to_db_a(self):
        line = [57515,'Sean','(780) 863-5715','estese@gmail.com','R1R','Dropoff','12/3/2014','']
        errors = []
        self.assertIsNotNone(reminders.csv_line_to_db(self.job_a['_id'],self.job_a['schema'],line, errors))

    def test_create_job(self):
        return True

if __name__ == '__main__':
    logger.info('********** begin reminders.py unittest **********')
    unittest.main()
