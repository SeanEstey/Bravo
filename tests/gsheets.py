import unittest
import sys
import os
import pymongo


from app import app
from tasks import celery_app
import gsheets

class BravoTestCase(unittest.TestCase):

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        celery_app.conf.CELERY_ALWAYS_EAGER = True
        mongo_client = pymongo.MongoClient(app.config['MONGO_URL'], app.config['MONGO_PORT'])
        self.db = mongo_client['test']

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

    '''
    def test_update_entry(self):
        self.assertTrue(gsheets.update_entry(
        'delivered', {
          'worksheet': 'Signups',
          'row': 3,
          'upload_status': 'Success',
        }
        ))
    '''

    def test_create_rfu(self):
        r = gsheets.create_rfu.apply_async(
          args=('vec', "Test RFU",),
          queue=app.config['DB'])

    '''
    def test_add_signup_view(self):
        r = self.app.post('/receive_signup', data=self.signup)
        self.assertEquals(r.status_code, 200)

    '''
    '''
    def test_add_signup(self):
        self.assertTrue(gsheets.add_signup(self.signup))
    '''

if __name__ == '__main__':
    mongo_client = pymongo.MongoClient(app.config['MONGO_URL'], app.config['MONGO_PORT'])
    gsheets.db = mongo_client['test']
    app.logger.info('********** begin gsheets unittest **********')
    unittest.main()
