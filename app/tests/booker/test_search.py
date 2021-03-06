'''app.tests.booker.test_search'''

import json
import pymongo
import unittest
from flask import Flask, Blueprint, request, url_for
from datetime import datetime, date, time, timedelta

from app import create_app
from app import gcal

class BookerSearchTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('app')
        self.app.testing = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()

        self.db = pymongo.MongoClient('localhost', 27017, tz_aware=True)['bravo']

        self.client.post(url_for('auth.login'), data=dict(
          username='sestey@vecova.ca',
          password='vec'
        ), follow_redirects=True)

        self.conf = self.db.agencies.find_one({'name':'vec'})

    def tearDown(self):
        response = self.client.get(url_for('auth.logout'),
        follow_redirects=True)

    # -------------------- HELPERS --------------------

    def update_db(self, collection, a_id, a_set):
        self.db[collection].update_one({'_id':a_id},{'$set':a_set})

    # -------------------- TESTS -----------------------

    def test_search(self):
        r = search.search('6348 33 Ave NW, Calgary, AB', None, None)
        print r

if __name__ == '__main__':
    unittest.main()
