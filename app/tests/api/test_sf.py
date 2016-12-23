'''app.tests.api.test_sf'''

import json
import pymongo
import unittest
from flask import Flask, Blueprint, request, url_for
from datetime import datetime, date, time, timedelta

from app import utils
from app import create_app
from app.api import salesforce

class SalesforceTests(unittest.TestCase):
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

        a = utils.start_timer()
        self.sf = salesforce.login()
        utils.end_timer(a, display=True, lbl='login time')

    def tearDown(self):
        response = self.client.get(url_for('auth.logout'),
        follow_redirects=True)

    # -------------------- HELPERS --------------------

    def update_db(self, collection, a_id, a_set):
        self.db[collection].update_one({'_id':a_id},{'$set':a_set})

    # -------------------- TESTS -----------------------

    def test_login(self):
        sf = salesforce.login()
        self.assertTrue(sf.session is not None)

    def test_add_contact(self):
        a = utils.start_timer()
        r = salesforce.add_contact(self.sf, {'LastName':'Smith','Email':'example@example.com'})
        utils.end_timer(a, display=True, lbl='add_contact')
        self.assertTrue(r['success'] == True)

    def test_get_contact(self):
        contact = salesforce.get_contact(self.sf, u'0034100000GAf2lAAD')

    def test_print_contact(self):
        #contact = salesforce.print_contact(self.sf, u'0034100000GAf2lAAD')
        return True

    def test_find_in_query(self):
        a = utils.start_timer()
        _id = u'0034100000GAf2lAAD'
        results = self.sf.query("SELECT Id, Email FROM Contact") # WHERE LastName = 'Jones'")
        utils.end_timer(a, display=True, lbl='query_time')

if __name__ == '__main__':
    unittest.main()
