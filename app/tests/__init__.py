'''app.tests.__init__'''
import json, logging, os
import celery.result
from datetime import datetime, date, time, timedelta
from flask import g, url_for
from flask_login import current_user, login_user
from app import create_app
from app.auth import load_user
from app.lib.mongo import create_client
import config

db_client = create_client(connect=True, auth=True)

ENVIRONS = {
    'BRV_SANDBOX': 'False',
    'BRV_TEST': 'True',
    'BRV_HTTP_HOST': 'http://bravotest.ca'
}

#-------------------------------------------------------------------------------
def get_db():
    return db_client[config.DB]

#-------------------------------------------------------------------------------
def init(self):
    self.app = create_app('app')
    #self.celery = init_celery(self.app)
    self.user_id = 'sestey@vecova.ca'
    self.client = self.app.test_client()
    self._ctx = self.app.test_request_context()
    self._ctx.push()
    g.db = self.db = self.app.db_client['bravo']
    g.group = 'vec'
    for k in ENVIRONS:
        os.environ[k] = ENVIRONS[k]

#-------------------------------------------------------------------------------
def login_self(self):
    self.user = load_user(self.user_id)
    login_user(self.user)
    g.user = self.user

#-------------------------------------------------------------------------------
def login_client(client):
    client.post(
        url_for('api._login_user'),
        data = dict(
            username='sestey@vecova.ca',
            password='Snookiecat@1'))

#-------------------------------------------------------------------------------
def logout(client):
    return client.post(
        url_for('api._logout_user'))
        #follow_redirects=True)

#-------------------------------------------------------------------------------
def update_db(db, collection, _id, kwargs):
    return db[collection].update_one({'_id':_id},{'$set':kwargs})

