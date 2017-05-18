'''app.mongodb'''
import logging
import pymongo
import db_auth
import config



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
        user or db_auth.user,
        pw or db_auth.password,
        mechanism='SCRAM-SHA-1')
