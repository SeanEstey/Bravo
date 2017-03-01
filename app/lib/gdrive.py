'''app.gdrive'''
import httplib2, json, logging, re, requests, pymongo
from oauth2client.service_account import ServiceAccountCredentials
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
from app import get_logger
log = get_logger('gdrive')


#-------------------------------------------------------------------------------
def gauth(oauth):
    scope = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]
    version = 'v3'
    name = 'drive'

    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            oauth,
            scopes=scope)
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build(name, version, http=http, cache_discovery=False)
    except Exception as e:
        log.error('Error authorizing %s: %s', name, str(e))
        return False

    #log.debug('drive service authorized')

    return service

#-------------------------------------------------------------------------------
def add_permissions(service, file_id, permissions):
    '''Add edit/owner permissions for new file
    @permissions: list of {'role':'owner/writer', 'email': ''} dicts
    @file_id: string google drive id
    https://developers.google.com/drive/v3/reference/permissions
    '''

    batch = service.new_batch_http_request()

    for p in permissions:
        if p['role'] == 'writer':
            batch.add(
              service.permissions().create(
                fileId = file_id,
                body={
                  'kind': 'drive#permission',
                  'type': 'user',
                  'role': p['role'],
                  'emailAddress': p['email']}),
              callback=permissions_callback)
        elif p['role'] == 'owner':
            batch.add(
              service.permissions().create(
                fileId = file_id,
                transferOwnership=True,
                body={
                  'kind': 'drive#permission',
                  'type': 'user',
                  'role': 'owner',
                  'emailAddress': p['email']}),
              callback=permissions_callback
            )

    http = httplib2.Http()
    batch.execute(http=http)

    return True

#-------------------------------------------------------------------------------
def permissions_callback(request_id, response, exception):
    '''
    batch.add() returns nothing. All response data returned here.
    batch.execute() also returns nothing.
    @request_id: string representing the nth command which raised exception
    @response:
    '''

    if exception is not None:
        log.error(
          'Request %s raised exception adding permissions: %s',
          request_id, str(exception))
        pass
    else:
        #log.debug(json.dumps(response))
        pass