import unittest
import json
import sys
import os
import time
import pymongo
import datetime
from dateutil.parser import parse
from werkzeug.datastructures import MultiDict
import xml.dom.minidom

#os.chdir('/home/sean/Bravo/flask')
#sys.path.insert(0, '/home/sean/Bravo/flask')

os.chdir('/root/bravo_dev/Bravo/flask')
sys.path.insert(0, '/root/bravo_dev/Bravo/flask')

from config import *
import reminders
import views
from app import flask_app, celery_app, log_handler

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

        self.job = {
          'schema': {
            "import_fields": [
              {"file_header":"Account","db_field":"account_id","type":"string","hide":True},
              {"file_header": "Name", "db_field": "name", "type":"string"},
              {"file_header": "Phone", "db_field": "call.to" ,"type":"string"},
              {"file_header": "Email", "db_field": "email.recipient", "type":"string"},
              {"file_header": "Block", "db_field": "custom.block", "type":"string"},
              {"file_header": "Status", "db_field": "custom.status", "type":"string"},
              {"file_header": "Next Pickup", "db_field": "custom.next_pickup",
                  "type":"date"},
              {"file_header": "Office Notes","db_field":"custom.office_notes",
                  "type":"string"}
            ],
            'call_template': 'speak/etw_reminder.html',
            'email_template': 'email/etw_reminder.html',
            'email_subject': 'A Subject'
          },
          'status': 'pending',
          'name': 'test',
          'fire_calls_dtime': parse('Dec 31, 2016'),
          'num_calls': 1
        }

        self.job_id = self.db['jobs'].insert(self.job)
        self.job = self.db['jobs'].find_one({'_id':self.job_id})

        self.reminder = {
            'job_id': self.job_id,
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

        # bson.objectid.ObjectId
        self.rem_id = self.db['reminders'].insert(self.reminder)

        self.reminder = self.db['reminders'].find_one({'_id':self.rem_id})

    # Remove job record created by setUp
    def tearDown(self):
        res = self.db['jobs'].remove({'_id':self.job_id})
        self.assertEquals(res['n'], 1)
        res = self.db['reminders'].remove({'_id':self.rem_id})
        self.assertEquals(res['n'], 1)

    def login(self, username, password):
        return self.app.post('/login', data=dict(
          username=username,
          password=password
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    '''
    def test_dial_valid(self):
        call = reminders.dial('7808635715')
        self.assertEquals(call.status, 'queued')
    '''
    '''
    def test_etw_reminder_human_answer_call(self):
        r = self.app.post('/reminders/call.xml', data={
          'CallSid': self.reminder['call']['sid'],
          'To': self.reminder['call']['to'],
          'CallStatus': 'in-progress',
          'AnsweredBy': 'human'
        })
        print "Human XML:" + r.data
    '''
    #'''
    def test_etw_reminder_machine_answer_call(self):
        r = self.app.post('/reminders/call.xml', data={
          'CallSid': self.reminder['call']['sid'],
          'To': self.reminder['call']['to'],
          'CallStatus': 'in-progress',
          'AnsweredBy': 'machine'
        })
        print "Machine XML:" + r.data
    #'''
    '''
    def test_dial_and_answer_call(self):
        call = reminders.dial(self.reminder['call']['to'])

        r = self.db['reminders'].update_one(
        {'_id':self.reminder['_id']},
        {'$set':{
          'call.sid':call.sid,
          'call.status': call.status
        }},
        )

        logger.info('SID: %s', call.sid)

        self.assertEquals(r.modified_count, 1)

        payload =  {
          'CallSid': call.sid,
          'To': self.reminder['call']['to'],
          'CallStatus': 'in-progress',
          'AnsweredBy': 'human'
        }

        r = self.app.post('/reminders/call.xml', data=dict(payload))

        xml_response = xml.dom.minidom.parseString(r.data)
        # Test valid XML returned by reminders.get_speak()
        self.assertTrue(isinstance(xml_response, xml.dom.minidom.Document))

        logger.info(r.data)
    '''
    '''
    def test_get_speak(self):
        r = self.app.post('/get_speak', data={
          'template': 'speak/etw_reminder.html',
          'reminder': reminders.bson_to_json(self.reminder)
        })
        self.assertTrue(type(r.data) == str)

        logger.info(r.data)
    '''
    '''
    def test_call_completed(self):
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
    '''
    #'''
    def test_send_calls(self):
        r = reminders.send_calls.apply_async(args=(str(self.job_id),),queue=DB_NAME)
        self.assertTrue(type(r.result), int)

    #'''
    '''
    def test_scheduler(self):
        # Tricky to test because it fires another sync call to execute_job
        # But the function returns num pending jobs. If we call it twice and
        # a job executes the first time, the second time it should
        #return a lower value for num pending jobs
        num_pending = tasks.run_scheduler() #.apply_async(queue=DB_NAME)
        num_pending2 = tasks.run_scheduler() #.apply_async(queue=DB_NAME)
        self.assertTrue(num_pending2 < num_pending)

    '''
    '''
    def test_execute_job(self):
        tasks.REDIAL_DELAY = 1
        r = tasks.execute_job(str(self.job_id))
        self.assertEquals(r, 'OK')
        time.sleep(3)
    '''
    '''
    def test_job_completion(self):
        completed_id = '54972d479b938767711838a0'
        res = requests.get(PUB_URL+'/complete/'+completed_id)
        self.assertEquals(res.status_code, 200)
    '''
    '''
    def test_many_calls(self):
        calls = []
        base = '780453'
        msg_document = {
        'job_id': self.job_id,
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

        for x in range(1000,1100):
          call = base + str(x)
          print call
          response = reminders.dial(call)
          #self.assertEquals(response['call_status'], 'queued', msg=response)
          sid = response['sid']
          msg_document['sid'] = sid
          msg_document['call_status'] = 'queued'
          msg_document['imported']['to'] = call
          print msg_document
          self.db['msgs'].insert(msg_document)
          payload = MultiDict([
          ('CallSid', response['sid']),
          ('To', call),
          ('CallStatus', 'in-progress'),
          ('AnsweredBy', 'human')
          ])
          del msg_document['_id']
          response = requests.post(PUB_URL+'/call/answer', data=payload)
          xml_response = xml.dom.minidom.parseString(response.text)
          # Test valid XML returned by reminders.get_speak()
          self.assertTrue(isinstance(xml_response, xml.dom.minidom.Document))
    '''
    '''
    def test_bravo_sms(self):
        self.msg['sms'] = True
        response = bravo.sms(self.msg['to'], 'sms unittest')
        self.assertEquals(response[0], 202, msg=json.dumps(response))
    '''
    '''
    def test_bravo_systems_check(self):
        self.assertTrue(bravo.systems_check)

    def test_bravo_fire_msg_voice(self):
        response = bravo.fire_msg(self.msg)
        self.assertNotEquals(response[0], 400)

    def test_get_speak_etw_active(self):
        speak = bravo.get_speak(self.job, self.msg)
        self.assertIsInstance(speak, str)

    def test_get_speak_etw_dropoff(self):
        self.msg['etw_status'] = 'Dropoff'
        speak = bravo.get_speak(self.job, self.msg)
        self.assertIsInstance(speak, str)

    def test_show_jobs_view(self):
        self.assertEqual(requests.get(PUB_URL+'/jobs').status_code, 200)

    def test_show_calls_view(self):
        uri = PUB_URL + '/jobs/' + str(self.job_id)
        self.assertEqual(requests.get(uri).status_code, 200)

    def test_parse_csv(self):
        from reminders import parse_csv
        import codecs
        from config import TEMPLATE_HEADERS
        filepath = '/tmp/ETW_Res_5E.csv'
        with codecs.open(filepath, 'r', 'utf-8-sig') as f:
          self.assertIsNotNone(parse_csv(f, TEMPLATE_HEADERS['etw_reminder']))

    def test_create_msg_record_etw_reminder(self):
        from reminders import create_msg_record
        buffer_row = [
        'Sean',
        '(780) 863-5715',
        'Dropoff',
        '12/3/2014',
        ''
        ]
        errors = []
        self.assertIsNotNone(create_msg_record(self.job, 1, buffer_row, errors))

    def test_create_msg_record_fake_date(self):
        from reminders import create_msg_record
        buffer_row = [
        'Sean',
        '(780) 863-5715',
        'Dropoff',
        '',
        ''
        ]
        errors = []
        create_msg_record(self.job, 1, buffer_row, errors)
        # Return invalid date error
        self.assertTrue(len(errors) > 0)

    def test_create_job(self):
        import requests

    def test_schedule_jobs_view(self):
        self.assertEqual(requests.get(PUB_URL+'/new').status_code, 200)

    def test_root_view(self):
        self.assertEquals(requests.get(PUB_URL).status_code, 200)

    def test_reminders_get_celery_status(self):
        self.assertEquals(requests.get(PUB_URL+'/get/celery_status').status_code, 200)

    def test_call_answer_get(self):
        from werkzeug.datastructures import MultiDict
        args='?CallStatus='+self.msg['status']+'&RequestUUID='+self.msg['request_uuid']+'&To='+self.msg['to']
        uri = PUB_URL + '/call/answer' + args
        self.assertEquals(requests.get(uri).status_code, 200)
'''

if __name__ == '__main__':
    logger.info('********** begin reminders.py unittest **********')
    unittest.main()