import pymongo
import logging
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
import re
import requests
import json

from app import app, db, info_handler, error_handler, debug_handler

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(debug_handler)
logger.setLevel(logging.DEBUG)


#-------------------------------------------------------------------------------
def gauth(oauth):
    scope = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]
    version = 'v3'
    name = 'drive'

    try:
        credentials = SignedJwtAssertionCredentials(
            oauth['client_email'],
            oauth['private_key'],
            scope
        )

        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build(name, version, http=http)
    except Exception as e:
        logger.error('Error authorizing %s: %s', name, str(e))
        return False

    logger.info('%s api authorized', name)

    return service

#-------------------------------------------------------------------------------
def add_permissions(service, file_id, permissions):
    '''Add edit/owner permissions for new file
    @permissions: list of {'role':'owner/writer', 'email': ''} dicts
    https://developers.google.com/drive/v3/reference/permissions
    '''

    #batch = service.new_batch_http_request()

    for p in permissions:
        #transferOwnership = False
        if p['role'] == 'writer':
            try:
                r = service.permissions().create(
                  fileId = file_id,
                  body={
                    'kind': 'drive#permission',
                    'type': 'user',
                    'role': p['role'],
                    'emailAddress': p['email']}
                  ).execute()
            except Exception as e:
                logger.error('Create permission error %s: %s', json.dumps(p), str(e))
                return False

            logger.info(json.dumps(r))
        # First add Writer permission, then transfer ownership
        elif p['role'] == 'owner':
            try:
                r = service.permissions().create(
                  fileId = file_id,
                  body={
                    'kind': 'drive#permission',
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': p['email']}
                  ).execute()
            except Exception as e:
                logger.error('Create permission error %s: %s', json.dumps(p), str(e))
                return False

            logger.info(json.dumps(r))

            permission_id = r['id']

            try:
                r = service.permissions().update(
                  fileId = file_id,
                  permissionId = permission_id,
                  transferOwnership = True,
                  body={
                    'role': 'owner'
                    }
                  ).execute()
            except Exception as e:
                logger.error('Create permission error %s: %s', json.dumps(p), str(e))
                return False

            logger.info(json.dumps(r))

    return True

#-------------------------------------------------------------------------------
def batch_callback(request_id, response, exception):
    if exception is not None:
        print str(exception)
        return False

    print request_id
    print response
    return response
