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
import views # Required for self.app.post()
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
        self.db = mongo_client[DB_NAME]

        self.signup = {
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
        }

    # Remove job record created by setUp
    def tearDown(self):
        foo = 'bar'

    def test_update_entry(self):
        self.assertTrue(gsheets.update_entry(
        'delivered', {
          'worksheet': 'Signups',
          'row': 3,
          'upload_status': 'Success',
        }
        ))

    def test_create_rfu(self):
        r = gsheets.create_rfu.apply_async(
          args=("Test RFU",),
          queue=DB_NAME)

    def test_add_signup_view(self):
        r = self.app.post('/receive_signup', data=self.signup)
        self.assertEquals(r.status_code, 200)

    def test_add_signup(self):
        self.assertTrue(gsheets.add_signup(self.signup))

if __name__ == '__main__':
    logger.info('********** begin gsheets unittest **********')
    unittest.main()