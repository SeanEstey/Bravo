'''app.tests.__init__'''
import os
from flask import g, url_for
from flask_login import current_user
from app import create_app, init_celery, is_test_server, config_test_server
import config
from app.mongodb import create_client

db_client = create_client(connect=True, auth=True)

ENVIRONS = {
    'BRAVO_SANDBOX_MODE': 'False',
    'BRAVO_TEST_SERVER': 'True',
    'BRAVO_HTTP_HOST': 'http://104.236.184.177'
}

def init_client(_self):
    '''Use in unittest setUp()
    '''
    _self.app = create_app('app', testing=True)
    _self.celery = init_celery(__name__, _self.app)
    _self.client = _self.app.test_client()
    _self._ctx = _self.app.test_request_context()
    _self._ctx.push()
    _self.db = g.db = get_db()

    for k in ENVIRONS:
        os.environ[k] = ENVIRONS[k]

def get_db():
    return db_client[config.DB]

def login(client):
    rv = client.post(
        url_for('auth.show_login'),
        data = dict(
            username='sestey@vecova.ca',
            password='vec'),
        follow_redirects=True)
    g.user = current_user

def logout(client):
    return client.get(
        url_for('auth.logout'),
        follow_redirects=True)

def update_db(db, collection, _id, kwargs):
    return db[collection].update_one({'_id':_id},{'$set':kwargs})

