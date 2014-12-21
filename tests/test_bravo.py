import unittest
import sys
import os
import plivo
os.chdir('/root/bravo')
sys.path.insert(0, '/root/bravo')

class BravoTestCase(unittest.TestCase):
  # Create mongodb connection, context to collection,
  # create a job record and handle
  def setUp(self):
    import pymongo
    import datetime
    self.client = pymongo.MongoClient('localhost', 27017)
    self.assertIsNotNone(self.client)
    self.db = self.client['wsf']
    self.assertIsNotNone(self.db)
    job_record = {
      'template': 'etw_reminder',
      'status': 'pending',
      'name': 'test',
      'fire_dtime': datetime.datetime(2014, 12, 31),
      'num_calls': 1
    }

    self.job_id = self.db['jobs'].insert(job_record)
    self.job = self.db['jobs'].find_one({'_id':self.job_id})
    self.assertIsNotNone(self.job_id)
    self.assertIsNotNone(self.job)
    from dateutil.parser import parse
    msg = {
      'job_id': self.job_id,
      'request_uuid': 'abc123',
      'status': 'not attempted',
      'attempts': 0,
      'event_date': parse('december 31, 2014'),
      'to': '780-555-5555',
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

  def test_bravo_dial(self):
    from bravo import dial
    import json
    response = dial(self.msg['to'])
    self.assertEquals(response[0], 201, msg=json.dumps(response))

  def test_bravo_sms(self):
    from bravo import sms
    import json
    self.msg['sms'] = True
    response = sms(self.msg['to'], 'sms unittest')
    self.assertEquals(response[0], 202, msg=json.dumps(response))

  def test_bravo_check_job_schedule(self):
    from bravo import check_job_schedule
    self.assertTrue(check_job_schedule())

  def test_bravo_systems_check(self):
    from bravo import systems_check
    self.assertTrue(systems_check);

  def test_bravo_fire_msgs(self):
    from bravo import fire_msgs
    self.assertTrue(fire_msgs(str(self.job_id)))

  def test_bravo_check_job_schedule(self):
    from bravo import check_job_schedule
    self.assertTrue(check_job_schedule())

  def test_bravo_job_summary(self):
    from bravo import create_job_summary
    self.assertTrue(create_job_summary(str(self.job_id)))

  def test_get_speak_etw_active(self):
    from bravo import get_speak
    speak = get_speak(self.job, self.msg)
    self.assertIsInstance(speak, str)

  def test_get_speak_etw_dropoff(self):
    from bravo import get_speak
    self.msg['etw_status'] = 'Awaiting Dropoff'
    speak = get_speak(self.job, self.msg)
    self.assertIsInstance(speak, str)

  def test_show_jobs_view(self):
    import requests
    url = 'http://localhost:5000/jobs'
    self.assertEqual(requests.get(url).status_code, 200)

  def test_show_calls_view(self):
    import requests
    url = 'http://localhost:5000/jobs/' + str(self.job_id)
    self.assertEqual(requests.get(url).status_code, 200)

  def test_parse_csv(self):
    from server import parse_csv
    import codecs
    from config import TEMPLATE_HEADERS
    filepath = '/tmp/ETW_Res_5E.csv'
    with codecs.open(filepath, 'r', 'utf-8-sig') as f:
      self.assertIsNotNone(parse_csv(f, TEMPLATE_HEADERS['etw_reminder']))

  def test_create_job(self):
    import requests
    #from dateutil.parser import parse
    #payload = MultiDict([
    #  ('date', parse('December 31, 2014')), 
    #  ('time', '3pm'), 
    #  ('CallStatus', self.msg['status'])
    #])

  def test_schedule_jobs_view(self):
    import requests
    url = 'http://localhost:5000/new'
    self.assertEqual(requests.get(url).status_code, 200)

  def test_root_view(self):
    import requests
    url = 'http://localhost:5000'
    self.assertEquals(requests.get(url).status_code, 200)

  def test_server_get_status(self):
    import requests
    url = 'http://localhost:5000/status'
    self.assertEquals(requests.get(url).status_code, 200)

  def test_server_get_celery_status(self):
    import requests
    url = 'http://localhost:5000/celery_status'
    self.assertEquals(requests.get(url).status_code, 200)

  def test_call_ring_post(self):
    from werkzeug.datastructures import MultiDict
    import requests
    url = 'http://localhost:5000/call/ring'
    payload = MultiDict([
      ('RequestUUID', self.msg['request_uuid']), 
      ('To', self.msg['to']), 
      ('CallStatus', self.msg['status'])
    ])
    self.assertEquals(requests.post(url, data=payload).status_code, 200)

  def test_call_answer_get(self):
    from werkzeug.datastructures import MultiDict
    import requests
    url = 'http://localhost:5000/call/answer'
    args='?CallStatus='+self.msg['status']+'&RequestUUID='+self.msg['request_uuid']+'&To='+self.msg['to']
    self.assertEquals(requests.get(url+args).status_code, 200)

  def test_call_hangup_post(self):
    from werkzeug.datastructures import MultiDict
    import requests
    self.db['msgs'].update(
      {'request_uuid':self.msg['request_uuid']},
      {'$set':{'code':'ANSWERED', 'status':'active'}})
    url = 'http://localhost:5000/call/hangup'
    self.msg = self.db['msgs'].find_one({'_id':self.msg_id})
    payload = MultiDict([
      ('RequestUUID', self.msg['request_uuid']), 
      ('To', self.msg['to']),
      ('HangupCause', 'NORMAL_CLEARING'),
      ('CallStatus', self.msg['status'])
    ])
    self.assertEquals(requests.post(url, data=payload).status_code, 200)

  def test_call_voicemail_post(self):
    from werkzeug.datastructures import MultiDict
    import requests
    payload = MultiDict([
      ('RequestUUID', self.msg['request_uuid']), 
      ('To', self.msg['to'])
    ])
    url = 'http://localhost:5000/call/voicemail'
    self.assertEquals(requests.post(url, data=payload).status_code, 200)

if __name__ == '__main__':
  from bravo import logger
  logger.info('********** begin unittest **********')
  unittest.main()