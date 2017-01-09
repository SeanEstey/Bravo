'''app.mongodb'''

import logging
import pymongo
import mongodb_auth
import config
#from . import utils, db
from flask import current_app, g
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def create_client(connect=False, auth=False):
    client = pymongo.MongoClient(
        host = config.MONGO_URL,
        port = config.MONGO_PORT,
        tz_aware = True,
        connect = connect)

    if auth:
        authenticate(client)

    return client

#-------------------------------------------------------------------------------
def authenticate(client):
    client.admin.authenticate(
        mongodb_auth.user,
        mongodb_auth.password,
        mechanism='SCRAM-SHA-1')
