import unittest
import sys
import os
import pymongo

#os.chdir('/home/sean/Bravo/flask')
#sys.path.insert(0, '/home/sean/Bravo/flask')

os.chdir('/root/bravo_dev/Bravo/flask')
sys.path.insert(0, '/root/bravo_dev/Bravo/flask')

from config import *
import scheduler
from app import logger, flask_app, celery_app

class BravoTestCase(unittest.TestCase):

  def setUp(self):
      flask_app.config['TESTING'] = True
      self.app = flask_app.test_client()
      celery_app.conf.CELERY_ALWAYS_EAGER = True
      ROUTE_IMPORTER_SHEET = 'Test Route Importer'

      mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
      self.db = mongo_client[DB_NAME]


  # Remove job record created by setUp
  def tearDown(self):
      foo = 'bar'

  '''def test_get_accounts(self):
      a = scheduler.get_accounts(days_from_now=4)
      self.assertEqual(type(a), list)
  '''

  '''def test_get_nps(self):
      a = scheduler.get_accounts(days_from_now=4)
      nps = scheduler.get_nps(a)
      self.assertEquals(type(nps), list)
  '''

  def test_analyze_nps(self):
      r = scheduler.analyze_non_participants.apply_async(
        queue=DB_NAME
      )

if __name__ == '__main__':
    logger.info('********** begin scheduler unittest **********')
    unittest.main()
