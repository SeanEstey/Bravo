'''app.tests.notify.test_tasks'''
import logging, unittest, json
from datetime import date
from flask import g
from app import get_logger
from app.tests import *
from app.notify.events import cancel_event, get_triggers
from app.notify.pickups import create_reminder
from app.notify.tasks import monitor_triggers, fire_trigger, schedule_reminders, skip_pickup
log = get_logger('tests.notify.tasks')

evnt_ids = []

class NotifyTasksTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)
        #evnt_ids.append(create_reminder('vec', 'R1Z', date(2017,4,2)))

    def tearDown(self):
        #for id_ in evnt_ids:
        #    cancel_event(id_)
        logout(self.client)

    def _test_monitor_triggers(self):
        try:
            monitor_triggers()
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_fire_trigger(self):
        try:
            evnt = self.db.events.find_one({'status':'pending'})
            tgrs = get_triggers(evnt['_id'])
            fire_trigger(tgrs[0]['_id'])
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def test_schedule_reminders(self):
        try:
            #r1z_date = date(2017,4,2)
            id_ = schedule_reminders.delay(agcy='vec') #, for_date=r1z_date)[0]
            evnt_ids.append(id_)
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
