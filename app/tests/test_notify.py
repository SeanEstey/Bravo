import json
import pymongo
from datetime import datetime, timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId
from bson.json_util import dumps


import unittest
from flask import Flask, Blueprint, request

from app import app
from app.notify import events
from app.notify import pickup_service
from app.notify import triggers


class NotifyTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

        #celery_app.conf.CELERY_ALWAYS_EAGER = True

        self.db = pymongo.MongoClient('localhost', 27017, tz_aware=True)['bravo']
        self.login('sestey@vecova.ca', 'vec')

    def tearDown(self):
        '''if hasattr(self, 'job_a'):
            self.db['jobs'].remove({'_id':self.job_a['_id']})
            self.db['reminders'].remove({'job_id':self.job_a['_id']})
        if hasattr(self, 'job_b'):
            self.db['jobs'].remove({'_id':self.job_b['_id']})
            self.db['reminders'].remove({'job_id':self.job_b['_id']})
        '''

    def insertJobsAndReminder(self):
        '''from data import job, reminder

        job_a_id = self.db['jobs'].insert_one(job).inserted_id
        del job['_id'] # insert_one modifies job and adds _id
        job['name'] = 'job_b'
        job_b_id = self.db['jobs'].insert_one(job).inserted_id
        self.job_a = self.db['jobs'].find_one({'_id':job_a_id})
        self.job_b = self.db['jobs'].find_one({'_id':job_b_id})
        reminder['job_id'] = self.job_a['_id']
        id = self.db['reminders'].insert_one(reminder).inserted_id
        self.reminder = self.db['reminders'].find_one({'_id':id})
        '''

    def update_db(self, collection, a_id, a_set):
        self.db[collection].update_one({'_id':a_id},{'$set':a_set})

    def login(self, username, password):
        return self.client.post('/login', data=dict(
          username=username,
          password=password
        ), follow_redirects=True)

    def test_get_notifications(self):
        evnt_id = ObjectId("57f735abfd9ab467f647cf8c")
        #print dumps(events.get_notifications(evnt_id, local_time=True),indent=4)
        return True

    def test_schedule_reminder(self):
        pickup_service.schedule_reminders()
        return True


    def test_get_trigger(self):
        _id = ObjectId("57f73508fd9ab4676e8817e6")
        #print dumps(triggers.get(_id), indent=4)
        return True


if __name__ == '__main__':
    # Use test endpoints
    INVALID_NUMBER = '+15005550001'
    UNROUTABLE_NUMBER = '+15005550002'

    unittest.main()
