import unittest
import sys
import os
import pymongo

#os.chdir('/home/sean/Bravo/flask')
#sys.path.insert(0, '/home/sean/Bravo/flask')

os.chdir('/root/bravo_dev/Bravo/flask')
sys.path.insert(0, '/root/bravo_dev/Bravo/flask')

from config import *
import gsheets
from app import logger, flask_app, celery_app

class BravoTestCase(unittest.TestCase):

  def setUp(self):
      flask_app.config['TESTING'] = True
      self.app = flask_app.test_client()
      celery_app.conf.CELERY_ALWAYS_EAGER = True

      mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
      self.db = mongo_client[DB_NAME]

  # Remove job record created by setUp
  def tearDown(self):
      foo = 'bar'

  def test_update_entry(self):
      self.assertTrue(gsheets.update_entry(
        'delivered', {
          'sheet': 'Route Importer',
          'worksheet': 'Signups',
          'row': 3,
          'upload_status': 'Success',
        }
      ))

  def test_create_rfu(self):
      self.assertTrue(gsheets.create_rfu("Test RFU"))

  def test_add_signup_row(self):
      self.assertTrue(gsheets.add_signup_row({
          'first_name': 'test',
          'last_name': 'mctesty',
          'account_type': 'Residential',
          'special_requests': 'get off my yard!',
          'address': '7444 104 st',
          'email': 'fake@fake.com',
          'phone': '780-123-4567',
          'postal': 'T6A 0P1',
          'tax_receipt': True,
          'city': 'Edmonton',
          'reason_joined': 'referral',
          'referrer': 'Good Samaritan'
      }))

if __name__ == '__main__':
    logger.info('********** begin gsheets unittest **********')
    unittest.main()
