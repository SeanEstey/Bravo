'''app.tests.notify.test_tasks'''
import logging, unittest, json
from datetime import date
from flask import g
from app.tests import *
from app.notify.tasks import monitor_triggers, fire_trigger, schedule_reminders, skip_pickup
log = logging.getLogger(__name__)

class NotifyTasksTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)

    def tearDown(self):
        logout(self.client)

    def _test_monitor_triggers(self):
        try:
            monitor_triggers()
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_fire_trigger(self):
        try:
            evnt_id = ''
            trig_id = ''
            fire_trigger(evnt_id, trig_id)
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def test_schedule_reminders(self):
        try:
            r1z_date = date(2017,4,2)
            schedule_reminders(agcy='vec', for_date=r1z_date)
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_skip_pickup(self):
        try:
            evnt_id = ''
            acct_id = ''
            skip_pickup(evnt_id, acct_id)
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

if __name__ == '__main__':
    unittest.main()
