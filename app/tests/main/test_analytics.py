'''app.tests.main.test_analytics'''
import logging, unittest, json
from flask import g
from app.tests.__init__ import *
from app import get_keys, get_logger
from app.main import analytics
log = get_logger('test_analytics')

class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)
        login_client(self.client)

    def tearDown(self):
        logout(self.client)

    def _test_store_accts(self):
        analytics.store_accts(blocks=['R8D', 'R10B'])

    def test_get_ytd_total(self):
        analytics.get_ytd_total('Ranchlands')

    def _test_update_ytd_total(self):
        analytics.update_ytd_total('Ranchlands')

if __name__ == '__main__':
    unittest.main()
