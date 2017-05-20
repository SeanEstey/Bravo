'''app.lib.mongodb'''
import logging
import pymongo
import db_auth
import config

#-------------------------------------------------------------------------------
def create_client(connect=True, auth=True, appname=None):

    client = pymongo.MongoClient(
        host = config.MONGO_URL,
        port = config.MONGO_PORT,
        tz_aware = True,
        connect = connect)
        #appname = appname or 'app')

    if auth:
        authenticate(client)

    return client

#-------------------------------------------------------------------------------
def authenticate(client, user=None, pw=None):

    try:
        client.admin.authenticate(
            user or db_auth.user,
            pw or db_auth.password,
            mechanism='SCRAM-SHA-1')
    except Exception as e:
        print 'Mongo authentication error: %s' % str(e)
        raise

    #print 'MongoClient authenticated'
