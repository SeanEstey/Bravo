'''app.tests.__init__'''
from flask import g, url_for
from flask_login import current_user
import config
from app.mongodb import create_client

db_client = create_client(connect=True, auth=True)

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

