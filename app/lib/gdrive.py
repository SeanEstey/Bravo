'''app.lib.gdrive'''
import logging
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def gauth(keyfile_dict):

    from .gservice_acct import auth
    return auth(
        keyfile_dict,
        name='drive',
        scopes=[
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file'],
        version='v3')

#-------------------------------------------------------------------------------
def add_permissions(service, file_id, permissions):
    '''Add edit/owner permissions for new file
    @permissions: list of {'role':'owner/writer', 'email': ''} dicts
    @file_id: string google drive id
    https://developers.google.com/drive/v3/reference/permissions
    '''

    import httplib2

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
        pass
