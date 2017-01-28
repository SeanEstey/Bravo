'''app.tests.main.test_email'''
import logging, unittest, json
from flask import g
from app.tests.__init__ import *
from app import get_keys, mailgun
log = logging.getLogger(__name__)

class EmailTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)
        login_client(self.client)

    def tearDown(self):
        logout(self.client)

    def test_send_email(self):
        try:
            test_db = db_client['test']
            conf = test_db.credentials.find_one({})['mailgun']
            rv = mailgun.send('sestey@vecova.ca', 'subject', 'hello', conf,
                v={'test_var':'hi', 'test_var_2':'bye'})
            print rv
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

if __name__ == '__main__':
    unittest.main()
