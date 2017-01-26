'''app.tests.api.test_sf'''

import json
import string
import requests
import pymongo
from random import randint
import random
import logging
import unittest
from flask import Flask, Blueprint, request, url_for
from datetime import datetime, date, time, timedelta

from app import utils
from app import create_app
from app.api import salesforce

log = logging.getLogger(__name__)

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

        self.sf = salesforce.login(sandbox=False)
    def tearDown(self):
        response = self.client.get(url_for('auth.logout'),
        follow_redirects=True)

    # -------------------- HELPERS --------------------

    def update_db(self, collection, a_id, a_set):
        self.db[collection].update_one({'_id':a_id},{'$set':a_set})

    def rnd_firstname(self):
        first = ['David', 'Jim', 'Elizabeth', 'Rebecca', 'Lindsay', 'Renee',
        'Matthew', 'Linda', 'Peter', 'Sarah', 'Ryan', 'Jeffrey', 'Alastair',
        'Derek', 'Simon', 'April']
        return first[randint(0, len(first)-1)]

    def rnd_lastname(self):
        last = ['Richardson', 'Palmer', 'Brown', 'Jones', 'Anderson',
        'Campbell', 'Jackson', 'Miller', 'Taylor', 'Cooper', 'Carson']
        return last[randint(0, len(last)-1)]

    def rnd_block(self):
        return 'R' + str(randint(1,9)) + random.choice(string.letters).upper()

    def rnd_address(self):
        return \
            str(randint(1000, 7000)) +' '+ str(randint(1, 99)) + ' ' +\
            random.choice(['St', 'Ave']) + ' ' + random.choice(['NW','NE','SW','SE'])

    def rnd_postal(self):
        return 'T' + str(randint(3,8)) + random.choice(string.letters).upper() +' '+\
        str(randint(1,9)) + random.choice(string.letters).upper() + str(randint(1,9))

    def rnd_email(self):
        first = ''.join(random.sample(string.letters, randint(6,11)))
        domain = random.choice(['gmail.com','hotmail.com','outlook.com','yahoo.ca','shaw.ca'])
        return first + '@' + domain

    def rnd_phone(self):
        return '403-' + str(randint(100,999)) + '-' + str(randint(1000,9999))

    def rnd_date(self):
        m = randint(1,12)
        str_m = '0'+str(m) if m < 10 else str(m)
        d=randint(1,31)
        str_d = '0'+str(d) if d < 10 else str(d)
        return '2017-'+str_m+'-'+str_d

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

    def test_match_records_by_block(self):
        a = utils.start_timer()
        r = salesforce.get_records(self.sf, block='R1A')
        utils.end_timer(a, display=True, lbl='get_records_by_block')
        self.assertTrue(len(r) > 0)

    '''
    #'''
    def test_add_acct(self):
        a = utils.start_timer()
        contact = {
            'FirstName': self.rnd_firstname(),
            'LastName': self.rnd_lastname(),
            'MailingStreet': self.rnd_address(),
            'MailingPostalCode': self.rnd_postal(),
            'MailingCity': 'Calgary',
            'MailingState': 'AB',
            'MailingCountry': 'Canada',
            'Email': self.rnd_email(),
            'MobilePhone': self.rnd_phone()
        }

        c_id = salesforce.add_account(
            self.sf,
            contact,
            self.rnd_block(),
            'Dropoff',
            'Arbour Lake',
            self.rnd_date()
        )
        utils.end_timer(a, display=True, lbl='add account')

        self.assertTrue(c_id is not False)
    #'''
    #'''
    def test_add_note(self):
        a = utils.start_timer()
        c_id = '0034100000GDjtXAAT' # jordan peterson
        salesforce.add_note(self.sf, c_id, 'a_title', 'note body')
        utils.end_timer(a, display=True, lbl='add note')
    #'''
    #'''
    def test_add_gift(self):
        a = utils.start_timer()
        c_id = '0034100000GDjtXAAT' # jordan peterson
        a_id = '0014100000DemvxAAB'
        campaign_id = '701410000005bXdAAI'

        salesforce.add_gift(
            self.sf, a_id, campaign_id,
            float(random.randrange(1.0, 50.0)),
            self.rnd_date(),
            '2 vb'
        )
        utils.end_timer(a, display=True, lbl='add gift')
    #'''


if __name__ == '__main__':
    unittest.main()
