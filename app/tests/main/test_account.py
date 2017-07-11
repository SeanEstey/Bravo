# app.tests.main.test_donors

import logging, unittest, json
from flask import g
from app.lib.dt import json_serial
from app.tests.__init__ import *
from app import get_keys
from app.main import etapestry
from app.main.account import Account
from logging import getLogger
log = getLogger(__name__)

class AccountTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)
        login_client(self.client)

    def tearDown(self):
        logout(self.client)

    def test_create_acct(self):
        account = Account(aid=5075, from_cache=False)
        pass

if __name__ == '__main__':
    unittest.main()
