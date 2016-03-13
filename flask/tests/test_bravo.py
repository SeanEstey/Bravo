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
os.chdir('/root/bravo')
sys.path.insert(0, '/root/bravo')

from config import *


class BravoTestCase(unittest.TestCase):
  def setUp(self):
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
    self.assertIsNotNone(self.job_id)
    self.assertIsNotNone(self.job)

    self.msg_document = {
      'job_id': self.job_id,
      'name': 'Test Res',
      'account_id': '57515',
      'event_date':
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
    self.msg_id = self.db['msgs'].insert(self.msg_document)
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

  def test_dial_valid(self):
    response = server.dial(self.msg['imported']['to'])
    self.assertEquals(response['call_status'], 'queued')
    return response

  def test_dial_invalid(self):
    response = server.dial('5005550002')
    self.assertEquals(response['call_status'], 'failed')
  
  def test_answer_call(self):
    response = server.dial(self.msg['imported']['to'])
    sid = response['sid']
    self.db['msgs'].update({'_id':self.msg['_id']},{'$set':{'sid': sid}})
    payload = MultiDict([
      ('CallSid', response['sid']), 
      ('To', self.msg['imported']['to']), 
      ('CallStatus', 'in-progress'),
      ('AnsweredBy', 'human')
    ])
    response = requests.post(PUB_URL+'/call/answer', data=payload)
    xml_response = xml.dom.minidom.parseString(response.text)
    # Test valid XML returned by server.get_speak() 
    self.assertTrue(isinstance(xml_response, xml.dom.minidom.Document))
    return sid
  
  def test_hangup_call(self):
    sid = self.test_answer_call()
    payload = MultiDict([
      ('To', self.msg['imported']['to']),
      ('CallSid', sid), 
      ('CallStatus', 'completed'),
      ('AnsweredBy', 'human'),
      ('CallDuration', 16)
    ])
    response = requests.post(PUB_URL+'/call/hangup', data=payload)
    self.assertEquals(response.content, 'OK')
  
  def test_scheduler(self):
    # Tricky to test because it fires another sync call to execute_job
    # But the function returns num pending jobs. If we call it twice and
    # a job executes the first time, the second time it should return a lower
    # value for num pending jobs
    num_pending = tasks.run_scheduler() #.apply_async(queue=DB_NAME)
    num_pending2 = tasks.run_scheduler() #.apply_async(queue=DB_NAME)
    print 'num_pending2='+str(num_pending2)+', num_pending1='+str(num_pending)
    self.assertTrue(num_pending2 < num_pending)

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
      response = server.dial(call)
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
      # Test valid XML returned by server.get_speak() 
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
    self.assertEqual(requests.get(PUB_URL+'/new').status_code, 200)

  def test_root_view(self):
    self.assertEquals(requests.get(PUB_URL).status_code, 200)

  def test_server_get_celery_status(self):
    self.assertEquals(requests.get(PUB_URL+'/get/celery_status').status_code, 200)
  
  def test_call_answer_get(self):
    from werkzeug.datastructures import MultiDict
    args='?CallStatus='+self.msg['status']+'&RequestUUID='+self.msg['request_uuid']+'&To='+self.msg['to']
    uri = PUB_URL + '/call/answer' + args
    self.assertEquals(requests.get(uri).status_code, 200)
  '''

if __name__ == '__main__':
  #bravo.set_mode('test')
  server.logger.info('********** begin unittest **********')
  unittest.main()
