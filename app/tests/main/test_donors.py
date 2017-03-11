'''app.tests.main.test_donors'''
import logging, unittest, json
from flask import g
from app.tests.__init__ import *
from app import get_keys, get_logger
from app.main import donors
log = get_logger('test_donors')

class DonorsTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)
        login_client(self.client)

    def tearDown(self):
        logout(self.client)

    def _test_save_rfu(self):
        print donors.save_rfu(6009, "test", "04/05/2017", fields={
            "Driver Notes":"RFU Test"})
    def test_prev_donation(self):
        print donors.get_prev_donation(
            5775,
            before=date.today()-timedelta(weeks=3))

if __name__ == '__main__':
    unittest.main()
