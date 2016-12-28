'''app.tests.api.test_sf'''

import json
import requests
import pymongo
import logging
import unittest
from flask import Flask, Blueprint, request, url_for
from datetime import datetime, date, time, timedelta

from app import utils
from app import create_app
from app.api import salesforce

logger = logging.getLogger(__name__)

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

    '''
    def test_login(self):
        sf = salesforce.login()
        self.assertTrue(sf.session is not None)

    def test_add_block(self):
        cm_id = '00v41000002sG1hAAE'
        #a = utils.start_timer()
        r = salesforce.add_block(self.sf, self.sf.CampaignMember.get(cm_id), 'B6A')
        self.assertTrue(r == 204)

    def test_rmv_block(self):
        cm_id = '00v41000002sG1hAAE'
        r = salesforce.rmv_block(self.sf, self.sf.CampaignMember.get(cm_id), 'B6A')
        self.assertTrue(r == 204)

    def test_get_records_by_block(self):
        a = utils.start_timer()
        r = salesforce.get_records(self.sf, block='R1A')
        utils.end_timer(a, display=True, lbl='get_records_by_block')
        self.assertTrue(len(r) > 0)
    '''

    def test_add_acct(self):
        contact = {
            'FirstName': 'Gerald',
            'LastName': 'Lewis',
            'MailingStreet': '6348 33 Ave NW',
            'MailingPostalCode': 'T3B 1K7',
            'MailingCity': 'Calgary',
            'MailingState': 'AB',
            'MailingCountry': 'Canada',
            'Email': 'estese@gmail.com',
            'MobilePhone': '403-289-6575'
        }

        c_id = salesforce.add_account(
            self.sf,
            contact,
            'R5A',
            'Dropoff',
            'Arbour Lake',
            '2016-06-21'
        )

        self.assertTrue(c_id is not False)

        print c_id

        import base64

        note = self.sf.ContentNote.create({
            'Content': base64.b64encode('Test test test'),
            'Title': 'No Pickup',
            'OwnerId': c_id
        })

        print note

        link = self.sf.ContentDocumentLink.create({
            'ContentDocumentId': note['id'],
            'LinkedEntityId': c_id,
            'ShareType': 'V'

        })

        print link

if __name__ == '__main__':
    unittest.main()
