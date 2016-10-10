'''tests.test_views'''

import json
import pymongo
import unittest
from flask import Flask, Blueprint, request, url_for

from app import create_app


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()

        #celery_app.conf.CELERY_ALWAYS_EAGER = True

        self.db = pymongo.MongoClient('localhost', 27017, tz_aware=True)['bravo']

        self.client.post(url_for('auth.login'), data=dict(
          username='sestey@vecova.ca',
          password='vec'
        ), follow_redirects=True)

    def tearDown(self):
        response = self.client.get(url_for('auth.logout'),
        follow_redirects=True)

    # -------------------- HELPERS --------------------

    def update_db(self, collection, a_id, a_set):
        self.db[collection].update_one({'_id':a_id},{'$set':a_set})


    # -------------------- TESTS -----------------------

    def test_main(self):
        response = self.client.get(url_for('notify.view_event_list'),
        follow_redirects=True)
        print 'test_main: %s' % str(response)

    def test_admin(self):
        response = self.client.get(url_for('main.view_admin'),
        follow_redirects=True)
        print 'test_admin: %s' % str(response)


if __name__ == '__main__':
    unittest.main()
