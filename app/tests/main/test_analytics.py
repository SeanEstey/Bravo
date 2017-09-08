# app.tests.main.test_analytics

import logging, unittest, json
from flask import g
from app.tests.__init__ import *
from app import get_keys
from app.main import etapestry
from app.main import analytics
from logging import getLogger
log = getLogger(__name__)

class AccountTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)
        login_client(self.client)

    def tearDown(self):
        logout(self.client)

    def test_gifts_dataset(self):
        r = analytics.gifts_dataset(
            start=date.today()-timedelta(days=365),
            end=date.today())

if __name__ == '__main__':
    unittest.main()
