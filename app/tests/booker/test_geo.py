'''app.tests.booker.test_geo'''

import json
import pymongo
import unittest
from flask import Flask, Blueprint, request, url_for
from datetime import datetime, date, time, timedelta

from app import create_app
from app import gcal


class BookerGeoTests(unittest.TestCase):
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

    def _test_find_block(self):
        block = geo.find_block(
            '6348 33 Ave NW, Calgary, AB',
            self.conf['google']['geocode']['api_key'])
        print block

    def test_get_nearby_blocks(self):
        events = gcal.get_events(
            gcal.gauth(self.conf['google']['oauth']),
            self.conf['cal_ids']['res'],
            datetime.today(),
            datetime.today() + timedelta(days=14)
        )

        results = geo.get_nearby_blocks(
            {'lat': 51.0825957,'lng':-114.1807788},
            10.0,
            self.db.maps.find_one({}),
            events
        )

if __name__ == '__main__':
    unittest.main()
