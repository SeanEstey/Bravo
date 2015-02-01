import unittest
import requests
import json
import sys
import os
import twilio
import pymongo
import json
import datetime
from dateutil.parser import parse
os.chdir('/root/bravo')
sys.path.insert(0, '/root/bravo')
from config import *
import tasks
import server
from server import dial

TWILIO_ACCOUNT_SID = 'AC4ca41ad0331210f865f3b966ceebe813'
TWILIO_AUTH_ID = '52ea057f9df92b65b9b990c669e4143c'

class BravoTestCase(unittest.TestCase):
  def setUp(self):
    job_document = {
      'template': 'etw_reminder',
      'status': 'pending',
      'name': 'test',
      'fire_dtime': datetime.datetime(2014, 12, 31),
      'num_calls': 1
    }
    
    self.pub_url = PUB_DOMAIN + ':' + str(PUB_TEST_PORT) + PREFIX 
    mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
    self.db = mongo_client[TEST_DB]
    self.job_id = self.db['jobs'].insert(job_document)
    self.job = self.db['jobs'].find_one({'_id':self.job_id})
    self.assertIsNotNone(self.job_id)
    self.assertIsNotNone(self.job)

    msg = {
      'job_id': self.job_id,
      'status': 'pending',
      'attempts': 0,
      'event_date': parse('december 31, 2014'),
      'to': '780-863-5715',
      'name': 'NIS',
      'etw_status': 'Active',
      'message': '',
      'office_notes': ''
    }
    self.msg_id = self.db['msgs'].insert(msg)
    self.msg = self.db['msgs'].find_one({'_id':self.msg_id})
    self.assertIsNotNone(self.msg_id)
    self.assertIsNotNone(self.msg)

  # Remove job record created by setUp
  def tearDown(self):
    import pymongo
    res = self.db['jobs'].remove({'_id':self.job_id})
    # n == num records deleted
    self.assertEquals(res['n'], 1)
    res = self.db['msgs'].remove({'_id':self.msg_id})
    self.assertEquals(res['n'], 1)

  def test_job_completion(self):
    completed_id = '54972d479b938767711838a0'
    res = requests.get(self.pub_url+'/complete/'+completed_id)
    self.assertEquals(res.status_code, 200)

  def test_bravo_dial(self):
    response = server.dial(self.msg['to'], self.pub_url)
    self.assertEquals(response[0], 201, msg=json.dumps(response))

  '''
  def test_bravo_sms(self):
    self.msg['sms'] = True
    response = bravo.sms(self.msg['to'], 'sms unittest')
    self.assertEquals(response[0], 202, msg=json.dumps(response))

  def test_bravo_systems_check(self):
    self.assertTrue(bravo.systems_check)

  def test_bravo_fire_msg_voice(self):
    response = bravo.fire_msg(self.msg)
    self.assertNotEquals(response[0], 400)
  
  def test_bravo_fire_msg_voice_no_phone(self):
    self.msg['to'] = ''
    response = bravo.fire_msg(self.msg)
    self.assertEquals(response[0], 400)
  
  def test_bravo_fire_msg_sms(self):
    self.msg['sms'] = 'true'
    response = bravo.fire_msg(self.msg)
    self.assertNotEquals(response[0], 400)

  def test_bravo_execute_job(self):
    self.assertTrue(bravo.execute_job(self.job_id))

  def test_get_speak_etw_active(self):
    speak = bravo.get_speak(self.job, self.msg)
    self.assertIsInstance(speak, str)

  def test_get_speak_etw_dropoff(self):
    self.msg['etw_status'] = 'Dropoff'
    speak = bravo.get_speak(self.job, self.msg)
    self.assertIsInstance(speak, str)

  def test_show_jobs_view(self):
    self.assertEqual(requests.get(self.pub_url+'/jobs').status_code, 200)

  def test_show_calls_view(self):
    uri = self.pub_url + '/jobs/' + str(self.job_id)
    self.assertEqual(requests.get(uri).status_code, 200)

  def test_parse_csv(self):
    from server import parse_csv
    import codecs
    from config import TEMPLATE_HEADERS
    filepath = '/tmp/ETW_Res_5E.csv'
    with codecs.open(filepath, 'r', 'utf-8-sig') as f:
      self.assertIsNotNone(parse_csv(f, TEMPLATE_HEADERS['etw_reminder']))

  def test_create_msg_record_etw_reminder(self):
    from server import create_msg_record
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
    from server import create_msg_record
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
    self.assertEqual(requests.get(self.pub_url+'/new').status_code, 200)

  def test_root_view(self):
    self.assertEquals(requests.get(self.pub_url).status_code, 200)

  def test_server_get_celery_status(self):
    self.assertEquals(requests.get(self.pub_url+'/get/celery_status').status_code, 200)
  
  def test_call_ring_post(self):
    from werkzeug.datastructures import MultiDict
    payload = MultiDict([
      ('RequestUUID', self.msg['request_uuid']), 
      ('To', self.msg['to']), 
      ('CallStatus', self.msg['status'])
    ])
    self.assertEquals(requests.post(self.pub_url+'/call/ring', data=payload).status_code, 200)
  
  def test_call_answer_get(self):
    from werkzeug.datastructures import MultiDict
    args='?CallStatus='+self.msg['status']+'&RequestUUID='+self.msg['request_uuid']+'&To='+self.msg['to']
    uri = self.pub_url + '/call/answer' + args
    self.assertEquals(requests.get(uri).status_code, 200)

  def test_call_answer_post(self):
    from werkzeug.datastructures import MultiDict
    payload = MultiDict([
      ('RequestUUID', self.msg['request_uuid']), 
      ('Digits', '1')
    ])
    response = requests.post(self.pub_url+'/call/answer', data=payload)
    self.assertEquals(response.status_code, 200)
  
  def test_machine_detect(self):
    from werkzeug.datastructures import MultiDict
    payload = MultiDict([
      ('RequestUUID', self.msg['request_uuid']), 
      ('CallUUID', self.msg['call_uuid']), 
      ('To', self.msg['to']) 
    ])
    res = requests.post(self.pub_url+'/call/machine', data=payload)
    self.assertEquals(res.status_code, 200)

  def test_call_hangup_post(self):
    from werkzeug.datastructures import MultiDict
    self.db['msgs'].update(
      {'request_uuid':self.msg['request_uuid']},
      {'$set':{'code':'ANSWERED', 'status':'IN_PROGRESS'}})
    self.msg = self.db['msgs'].find_one({'_id':self.msg_id})
    payload = MultiDict([
      ('RequestUUID', self.msg['request_uuid']), 
      ('To', self.msg['to']),
      ('HangupCause', 'NORMAL_CLEARING'),
      ('CallStatus', self.msg['status'])
    ])
    try:
      response = requests.post(self.pub_url+'/call/hangup', data=payload)
      self.assertEquals(response.status_code, 200)
    except Exception as e:
      self.fail('hangup exception')

  def test_call_voicemail_post(self):
    from werkzeug.datastructures import MultiDict
    payload = MultiDict([
      ('RequestUUID', self.msg['request_uuid']), 
      ('To', self.msg['to'])
    ])
    self.assertEquals(requests.post(self.pub_url+'/call/voicemail', data=payload).status_code, 200)
  '''

if __name__ == '__main__':
  #bravo.set_mode('test')
  server.logger.info('********** begin unittest **********')
  unittest.main()
