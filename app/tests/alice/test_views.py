'''app.tests.alice.test_views'''

import json
import logging
import pymongo
import os
import unittest
from simplekv.db.mongo import MongoStore
from flask_kvsession import KVSessionExtension
from flask_login import current_user
from flask import g, session, request, url_for
from flask import has_app_context, has_request_context
from datetime import datetime, date, time, timedelta
import config
from app import mongodb, kv_ext, db_client, create_app
from app import is_test_server,config_test_server
import app.alice.session
log = logging.getLogger(__name__)

msg = {
    'FromZip':u'',
    'From':u'+17808635715',
    'SmsMessageSid':u'SMe236c86aec9f03fd43ecc8b790e72302',
    'FromCity': u'EDMONTON',
    'ApiVersion':u'2010-04-01',
    'To':u'+15873192488',
    'NumMedia': u'0',
    'NumSegments':u'1',
    'AccountSid':u'ACcc7d275199429677243e3b9ee7936488',
    'SmsSid':u'SMe236c86aec9f03fd43ecc8b790e72302',
    'ToCity':u'Calgary',
    'FromState':u'AB',
    'FromCountry':u'CA',
    'Body':u'',
    'MessageSid':u'SMe236c86aec9f03fd43ecc8b790e72302',
    'SmsStatus': u'received',
    'ToZip':u'',
    'ToCountry':u'CA',
    'ToState':u'Alberta'
}

class AliceViewsTests(unittest.TestCase):
    def setUp(self):
        if is_test_server():
            config_test_server('test_server')
        self.app = create_app('app')
        self.app.testing = True

        self.app_context = self.app.app_context()
        self.app_context.push()

        self.client = self.app.test_client()

        kv_ext.init_app(self.app)

        g.db = db_client['bravo']
        g.user = current_user

        self._ctx = self.app.test_request_context()
        self._ctx.push()

        self.client.post(url_for('auth.login'), data=dict(
          username='sestey@vecova.ca',
          password='vec'
        ))#, follow_redirects=True)

    def tearDown(self):
        response = self.client.get(url_for('auth.logout'), follow_redirects=True)
        pass

    # -------------------- TESTS -----------------------

    #def test_dump_session(self):
    #    a = self.client.get(url_for('alice.show_chatlogs'))

    def test_skip_thanks(self):
        msg['Body'] = 'skip this one'
        self.client.post('/alice/vec/receive', data=msg)
        msg['Body'] = 'thanks'
        self.client.post('/alice/vec/receive', data=msg)

    def test_instructions(self):
        msg['Body'] = 'instructions'
        self.client.post('/alice/vec/receive', data=msg)
        msg['Body'] = 'go to hell'
        self.client.post('/alice/vec/receive', data=msg)

if __name__ == '__main__':
    unittest.main()
