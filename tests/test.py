import unittest
import sys
sys.path.insert(0, '/root/bravo')
from bravo import getSpeak

"""Tests for `bravo.py`."""
class BravoTestCase(unittest.TestCase):
  def test_getSpeak(self):
    job = {
      'template': 'etw_reminder',
      'message': 'this is a special msg'
    }
    self.assertIsInstance(getSpeak(job, 'Awaiting Dropoff', '12/3/2014'), str)
    self.assertFalse(getSpeak(job, 'Awaiting Dropoff', 'Not a date'), msg='Fake date')

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
    import requests
    import json
    url = 'http://localhost:5000/call/ring'
    payload = { 'RequestUUID':'abc123', 'To':'7801234567', 'CallStatus':'bla' }
    headers = { 'content-type':'application/json' }
    self.assertEquals(requests.post(url, data=json.dumps(payload), headers=headers).status_code, 200)


if __name__ == '__main__':
  unittest.main()
