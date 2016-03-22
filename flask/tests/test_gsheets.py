import unittest
import sys
import os
import pymongo

os.chdir('/home/sean/Bravo/flask')
sys.path.insert(0, '/home/sean/Bravo/flask')
#os.chdir('/root/bravo_experimental/Bravo/flask')
#sys.path.insert(0, '/root/bravo_experimental/Bravo/flask')

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
      # .placeholder

  def test_update_entry(self):
      self.assertTrue(gsheets.update_entry({
        'sheet_name': 'Route Importer',
        'worksheet_name': 'Signups',
        'row': 3,
        'upload_status': 'Success'
      }))
  
  def test_create_rfu(self):
      self.assertTrue(gsheets.create_rfu("Test RFU"))
  
  def test_add_signup_row(self):
      self.assertEquals(r.status_code, 200)

if __name__ == '__main__':
    logger.info('********** begin views.py unittest **********')
    unittest.main()
