import json
import pymongo
from datetime import datetime, timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId
from bson.json_util import dumps


import unittest
from flask import Flask, Blueprint, request

from app import app
from app.notify import notific_events


class NotifyTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

        #celery_app.conf.CELERY_ALWAYS_EAGER = True

        self.db = pymongo.MongoClient('localhost', 27017)['bravo']
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

    def test_first(self):
        event_id = ObjectId("57f64ad7fd9ab44c64784ef3")
        print dumps(notific_events.get_grouped_notifications(event_id),
                sort_keys=True, indent=4)
        return True



if __name__ == '__main__':
    #mongo_client = pymongo.MongoClient(app.config['MONGO_URL'], app.config['MONGO_PORT'])
    #reminders.db = mongo_client['test']

    # Use test endpoints
    #reminders.TWILIO_ACCOUNT_SID = app.config['TWILIO_TEST_ACCOUNT_SID']
    #reminders.TWILIO_AUTH_ID = app.config['TWILIO_TEST_AUTH_ID']
    #reminders.FROM_NUMBER = '+15005550006'
    INVALID_NUMBER = '+15005550001'
    UNROUTABLE_NUMBER = '+15005550002'


    # Set logger to redirect to tests.log
    #test_log_handler = logging.FileHandler(app.config['LOG_PATH'] + 'tests.log')
    #reminders.logger.handlers = []
    #reminders.logger = logging.getLogger(reminders.__name__)
    #reminders.logger.addHandler(test_log_handler)
    #reminders.logger.setLevel(logging.DEBUG)

    #now = datetime.now()
    #reminders.logger.info(now.strftime('\n[%m-%d %H:%M] *** STARTING REMINDERS UNIT TEST ***\n'))

    unittest.main()
