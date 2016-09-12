import pymongo
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest

client = pymongo.MongoClient('localhost', 27017)
db = client['bravo']


def auth_gservice(name):
    if name == 'sheets':
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        version = 'v4'
    elif name == 'drive':
        scope = ['https://www.googleapis.com/auth/drive',
         'https://www.googleapis.com/auth/drive.file']
        version = 'v3'
    elif name == 'calendar':
       scope = ['https://www.googleapis.com/auth/calendar.readonly']
       version = 'v3'

    oauth = db['agencies'].find_one({'name': 'vec'})['oauth']

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
        print('Error authorizing %s: %s', name, str(e))
        return False

    print 'Authorized'

    return service


def make_route_file(title):
    '''Make copy of Route Template, add edit/owner permissions
    Uses batch request for creating permissions
    '''

    service = auth_gservice('drive')

    template_id = db['agencies'].find_one({'name':'vec'})['routing']['gdrive_template_id']

    # Copy Route Template
    file_copy = service.files().copy(
      fileId=template_id,
      body={
        'name': title
      }
    ).execute()

    print file_copy

    # Add edit/owner permissions for new file
    permissions = db['agencies'].find_one({'name':'vec'})['routing']['permissions']

    batch = service.new_batch_http_request()

    for p in permissions:
        transferOwnership = False

        if p['role'] == 'owner':
            transferOwnership = True

        batch.add(service.permissions().create(
          fileId = file_copy['id'],
          transferOwnership = transferOwnership,
          body={
            'kind': 'drive#permission',
            'type': 'user',
            'role': p['role'],
            'emailAddress': p['email']}),
          callback=batch_callback)

    http = httplib2.Http()
    batch.execute(http=http)

    routed_folder_id = db['agencies'].find_one({'name':'vec'})['routing']['routed_folder_id']

    # Retrieve the existing parents to remove
    file = service.files().get(
      fileId=file_copy['id'],
      fields='parents').execute()

    previous_parents = ",".join(file.get('parents'))

    # Move the file to the new folder
    file = service.files().update(
      fileId=file_copy['id'],
      addParents=routed_folder_id,
      removeParents=previous_parents,
      fields='id, parents').execute()


def batch_callback(request_id, response, exception):
    if exception is not None:
        print str(exception)
        return False

    print request_id
    print response
    return response


def write_sheet(ss_id):
    service = auth_gservice('sheets')

    # Call bravoweb.ca/routing/get_route/<job_id>

    # Write those orders to the sheet

    service.spreadsheets().values().update(
      spreadsheetId=ss_id,
      valueInputOption = "USER_ENTERED",
      range="A1:D5",
      body={
        "majorDimension": "ROWS",
        "values": [
          ["Item", "Cost", "Stocked", "Ship Date"],
          ["Wheel", "$20.50", "4", "3/1/2016"],
          ["Door", "$15", "2", "3/15/2016"],
          ["Engine", "$100", "1", "30/20/2016"],
          ["Totals", "=SUM(B2:B4)", "=SUM(C2:C4)", "=MAX(D2:D4)"]
        ]
      }
    ).execute()


#make_route_file("FOOOBAR")
write_sheet("19V5kwo3AczZoYXUdQ6_8oGkkDni-CVTDcH3p5Hjy-BE")
