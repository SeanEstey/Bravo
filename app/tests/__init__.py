'''app.tests.__init__'''
import json, logging, os
import celery.result
from datetime import datetime, date, time, timedelta
from flask import g, url_for
from flask_login import current_user, login_user
from app import create_app, init_celery
from app.auth import load_user
from app.lib.mongodb import create_client
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
    self.app = create_app('app', testing=True)
    self.celery = init_celery(self.app)
    self.user_id = 'sestey@vecova.ca'
    self.client = self.app.test_client()
    self._ctx = self.app.test_request_context()
    self._ctx.push()
    self.db = g.db = get_db()
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
        url_for('auth.authenticate'),
        data = dict(
            username='sestey@vecova.ca',
            password='vec'))

#-------------------------------------------------------------------------------
def logout(client):
    return client.post(
        url_for('auth.logout'))
        #follow_redirects=True)

#-------------------------------------------------------------------------------
def update_db(db, collection, _id, kwargs):
    return db[collection].update_one({'_id':_id},{'$set':kwargs})

