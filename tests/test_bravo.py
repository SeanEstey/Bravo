import unittest
import sys
sys.path.insert(0, '/root/bravo')
from bravo import getSpeak

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

  def test_getSpeak_dropoff(self):
    speak = getSpeak(self.job, 'Awaiting Dropoff', self.job['fire_dtime'])
    self.assertIsInstance(speak, str)

  def test_getSpeak_invalid_date(self):
    try:
      getSpeak(self.job, 'Awaiting Dropoff', 'DECLEMBER 5, 2014')
    except AttributeError:
      pass
    else:
      self.fail('AttributeError not thrown')

  def test_show_jobs_view(self):
    import requests
    url = 'http://localhost:5000/jobs'
    self.assertEqual(requests.get(url).status_code, 200)

  def test_show_calls_view(self):
    import requests
    url = 'http://localhost:5000/jobs/' + str(self.job_id)
    self.assertEqual(requests.get(url).status_code, 200)

  def test_schedule_jobs_view(self):
    import requests
    url = 'http://localhost:5000/new'
    self.assertEqual(requests.get(url).status_code, 200)

  def test_root_view(self):
    import requests
    url = 'http://localhost:5000'
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
  unittest.main()
