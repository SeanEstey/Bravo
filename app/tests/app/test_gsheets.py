'''app.tests.gsheets'''
import json
import pymongo
import unittest
from flask import Flask, Blueprint, request, url_for
from datetime import datetime, date, time, timedelta

from app import create_app
from app import gsheets
from app import db

class GSheetsTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('app')
        self.app.testing = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()

        self.db = db

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

    def test_insert_rows(self):
        ss_id = '1fo3ATjdWlIdtePVyYM8Xwrm1GDpYS8aUry0dnTWVXBQ'
        conf = self.db.agencies.find_one({'name':'vec'})
        service = gsheets.gauth(conf['google']['oauth'])
        gsheets.insert_rows_above(service, ss_id, 44, 1)

if __name__ == '__main__':
    unittest.main()
