'''app.tests.main.test_tasks'''
import logging, unittest, json
from flask import g
from app.tests.__init__ import *
from app.main import tasks
log = logging.getLogger(__name__)

class MainTasksTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)

    def tearDown(self):
        logout(self.client)

    def test_find_inactive_donors(self):
        try:
            tasks.find_inactive_donors(agcy='vec', in_days=-2, max_inactive_days=5)
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)
    def _test_send_receipts(self):
        try:
            print 'dome'
            #tasks.send_receipts()
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)
    def _test_create_rfu(self):
        try:
            tasks.create_rfu(
                'vec', 'Non-participant. No collection',
                options={
                    'Account Number': 269,
                    'Block': 'R6A',
                    'Driver Notes': 'foo',
                    'Office Notes': 'bar'})
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_update_accts_sms(self):
        try:
            print 'do me'
            #tasks.update_accts_sms(agcy='vec')
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

if __name__ == '__main__':
    unittest.main()
