'''app.tests.main.test_tasks'''
import logging, unittest, json
from datetime import datetime, date, timedelta
from flask import g
from app.tests.__init__ import *
from app.main import tasks
from logging import getLogger
log = getLogger(__name__)

class MainTasksTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)

    def tearDown(self):
        logout(self.client)

    def test_find_inactive_delay(self):
        try:
            tasks.find_inactive_donors.delay(agcy='vec', in_days=2, period=270)
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_send_receipts(self):
        entry = {
            'agcy': 'vec',
            'acct_id': 269,
            'date': '1/23/2017',
            'amount': 6.00,
            'next_pickup': '4/17/2017',
            'status': 'Active',
            'from_row': 2}

        try:
            tasks.send_receipts([entry])
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_create_rfu(self):
        try:
            tasks.create_rfu(
                'vec', 'Non-participant. No collection',
                options={
                    'ID': 269,
                    'Block': 'R6A',
                    'Driver Notes': 'foo',
                    'Office Notes': 'bar'})
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_create_rfu_delay(self):
        try:
            tasks.create_rfu.delay(
                'vec', 'Testing celery worker delay()',
                options={
                    'ID': 269,
                    'Block': 'R6A',
                    'Driver Notes': 'foo',
                    'Office Notes': 'bar'})
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_update_accts_sms(self):
        try:
            print 'WRITE ME'
            #tasks.update_accts_sms(agcy='vec')
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_update_cal_routes(self):
        try:
            tasks.update_calendar_blocks(
                from_=date(2017,4,24),
                to=date(2017,4,28))
        except Exception as e:
            log.debug('err=%s', str(e), exc_info=True)

    def _test_etw_add_form_signup(self):
        data={
            u'city': u'Edmonton',
            u'first_name': u'Test', u'last_name': u'Test', u'account_type':
            u'Residential', u'special_requests': u'', u'title': u'Mr',
            u'referrer': u'', u'tax_receipt': u'Yes', u'email':
            u'test@fake.com', u'phone': u'780-123-4567', u'address': u'Test',
            u'reason_joined': u'Facebook', u'contact_person': u'', u'postal':
            u'T5K 9F9', u'account_name': u''}
        try:
            tasks.add_form_signup(data)
        except Exception as e:
            log.debug('err=%s', str(e), exc_info=True)



if __name__ == '__main__':
    unittest.main()
