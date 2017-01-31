'''app.mongodb'''

import logging
import pymongo
import mongodb_auth
import config
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def create_client(connect=True, auth=True):
    client = pymongo.MongoClient(
        host = config.MONGO_URL,
        port = config.MONGO_PORT,
        tz_aware = True,
        connect = connect)

    if auth:
        authenticate(client)

    return client

#-------------------------------------------------------------------------------
def authenticate(client, user=None, pw=None):
    client.admin.authenticate(
        user or mongodb_auth.user,
        pw or mongodb_auth.password,
        mechanism='SCRAM-SHA-1')
