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

  # Remove job record created by setUp
  def tearDown(self):
    import pymongo
    res = self.db['jobs'].remove({'_id':self.job_id})
    # n == num records deleted
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
    url = 'http://localhost:5000/jobs/549323dd9b93873a54f1c0ab'
    self.assertEqual(requests.get(url).status_code, 200)

  def test_schedule_jobs_view(self):
    import requests
    url = 'http://localhost:5000/new'
    self.assertEqual(requests.get(url).status_code, 200)

  def test_root_view(self):
    import requests
    url = 'http://localhost:5000'
    self.assertEquals(requests.get(url).status_code, 200)

  def test_call_ring(self):
    from werkzeug.datastructures import MultiDict
    import requests
    url = 'http://localhost:5000/call/ring'
    payload = MultiDict([
      ('RequestUUID','abc123'), 
      ('To','7801234567'), 
      ('CallStatus','bla')
    ])
    self.assertEquals(requests.post(url, data=payload).status_code, 200)


if __name__ == '__main__':
  unittest.main()
