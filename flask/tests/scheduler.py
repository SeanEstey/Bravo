import unittest
import sys
import os
import pymongo
from datetime import datetime, timedelta

os.chdir('/root/bravo_dev/Bravo/flask')
sys.path.insert(0, '/root/bravo_dev/Bravo/flask')

from app import app
from tasks import celery_app
import scheduler

class BravoTestCase(unittest.TestCase):

    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        celery_app.conf.CELERY_ALWAYS_EAGER = True
        mongo_client = pymongo.MongoClient(app.config['MONGO_URL'], app.config['MONGO_PORT'])
        self.db = mongo_client['test']

        ROUTE_IMPORTER_SHEET = 'Test Route Importer'

    # Remove job record created by setUp
    def tearDown(self):
        foo = 'bar'

    def testGetCalEvents(self):
        r = scheduler.get_cal_events(
            self.db['agencies'].find_one({'name':'vec'})['cal_ids']['res'],
            datetime.now() + timedelta(days=1),
            datetime.now() + timedelta(days=2),
            self.db['agencies'].find_one({'name':'vec'})['oauth'])
        app.logger.info(r)

    '''def test_get_accounts(self):
        a = scheduler.get_accounts(days_from_now=4)
        self.assertEqual(type(a), list)
    '''

    '''def test_get_nps(self):
        a = scheduler.get_accounts(days_from_now=4)
        nps = scheduler.get_nps(a)
        self.assertEquals(type(nps), list)
    '''
    '''
    def test_analyze_nps(self):
        r = scheduler.analyze_non_participants.apply_async(
        queue=DB_NAME
        )
    '''

if __name__ == '__main__':
    app.logger.info('********** begin scheduler unittest **********')
    unittest.main()
