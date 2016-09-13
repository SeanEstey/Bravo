import pymongo
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
import re
import requests
import json

#client = pymongo.MongoClient('localhost', 27017)
#db = client['bravo']

from app import app, db, info_handler, error_handler, debug_handler, login_manager

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(debug_handler)
logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
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

#-------------------------------------------------------------------------------
def add_permissions(drive_api, file_id, permissions):
    '''
    @permissions: dict of {'role':'owner/writer', 'email': ''} for each user
    '''

    # Add edit/owner permissions for new file

    batch = drive_api.new_batch_http_request()

    for p in permissions:
        transferOwnership = False

        if p['role'] == 'owner':
            transferOwnership = True

        batch.add(drive_api.permissions().create(
          fileId = file_id,
          transferOwnership = transferOwnership,
          body={
            'kind': 'drive#permission',
            'type': 'user',
            'role': p['role'],
            'emailAddress': p['email']}),
          callback=batch_callback)

    http = httplib2.Http()
    batch.execute(http=http)

    return True

#-------------------------------------------------------------------------------
def create_sheet(drive_api, title):
    '''Make copy of Route Template, add edit/owner permissions
    Uses batch request for creating permissions
    Returns: ID of new Sheet file
    '''

    template_id = db['agencies'].find_one({'name':'vec'})['routing']['gdrive_template_id']

    # Copy Route Template
    file_copy = drive_api.files().copy(
      fileId=template_id,
      body={
        'name': title
      }
    ).execute()

    print file_copy

    routed_folder_id = db['agencies'].find_one({'name':'vec'})['routing']['routed_folder_id']

    # Retrieve the existing parents to remove
    file = drive_api.files().get(
      fileId=file_copy['id'],
      fields='parents').execute()

    previous_parents = ",".join(file.get('parents'))

    # Move the file to the new folder
    file = drive_api.files().update(
      fileId=file_copy['id'],
      addParents=routed_folder_id,
      removeParents=previous_parents,
      fields='id, parents').execute()

    return file_copy['id']


#-------------------------------------------------------------------------------
def batch_callback(request_id, response, exception):
    if exception is not None:
        print str(exception)
        return False

    print request_id
    print response
    return response


#-------------------------------------------------------------------------------
def write_sheet(sheets_api, ss_id, route_id):
    r = requests.get("http://www.bravoweb.ca/routing/get_route/" + route_id)
    orders = json.loads(r.text)

    # Write those orders to the sheet

    rows = []

    orders = orders[1:-1]

    num_orders = len(orders)

    for order in orders:
        addy = order['location_name'].split(', ');

        # Remove Postal Code from Google Maps URL label
        if re.match(r'^T\d[A-Z]$', addy[-1]) or re.match(r'^T\d[A-Z]\s\d[A-Z]\d$', addy[-1]):
           addy.pop()

        formula = '=HYPERLINK("' + order['gmaps_url'] + '","' + ", ".join(addy) + '")'

        '''
        Info Column format (column D):

        Notes: Fri Apr 22 2016: Pickup Needed
        Name: Cindy Borsje

        Neighborhood: Lee Ridge
        Block: R10Q,R8R
        Contact (business only): James Schmidt
        Phone: 780-123-4567
        Email: Yes/No
        '''

        order_info = ''

        if order['customNotes'].get('driver notes'):
          order_info += 'NOTE: ' + order['customNotes']['driver notes'] + '\n\n'

          #sheet.getRange(i+2, headers.indexOf('Order Info')+1).setFontWeight("bold");

          if order['customNotes']['driver notes'].find('***') > -1:
            order_info = order_info.replace("***", "")
            #sheet.getRange(i+2, headers.indexOf('Order Info')+1).setFontColor("red");

        order_info += 'Name: ' + order['customNotes']['name'] + '\n'

        if order['customNotes'].get('neighborhood'):
          order_info += 'Neighborhood: ' + order['customNotes']['neighborhood'] + '\n'

        order_info += 'Block: ' + order['customNotes']['block']

        if order['customNotes'].get('contact'):
          order_info += '\nContact: ' + order['customNotes']['contact']

        if order['customNotes'].get('phone'):
          order_info += '\nPhone: ' + order['customNotes']['phone']

        if order['customNotes'].get('email'):
          order_info += '\nEmail: ' + order['customNotes']['email']

        order_info += '\nArrive: ' + order['arrival_time']

        rows.append([
          formula,
          '',
          '',
          order_info,
          order['customNotes'].get('id') or '',
          order['customNotes'].get('driver notes') or '',
          order['customNotes'].get('block') or '',
          order['customNotes'].get('neighborhood') or '',
          order['customNotes'].get('status') or '',
          order['customNotes'].get('office notes') or ''
        ])

    # Start from Row 2 Column A to Column J
    _range = "A2:J" + str(num_orders+1)

    write_rows(sheets_api, ss_id, rows, _range)

    values = get_values(sheets_api, ss_id, "A1:$A")

    hide_start = 1 + len(rows) + 1;
    hide_end = values.index(['***Route Info***'])

    hide_rows(sheets_api, ss_id, hide_start, hide_end)


#-------------------------------------------------------------------------------
def write_rows(sheets_api, ss_id, rows, a1_range):
    sheets_api.spreadsheets().values().update(
      spreadsheetId = ss_id,
      valueInputOption = "USER_ENTERED",
      range = a1_range,
      body = {
        "majorDimension": "ROWS",
        "values": rows
      }
    ).execute()


#-------------------------------------------------------------------------------
def get_values(sheets_api, ss_id, a1_range):
    values = sheets_api.spreadsheets().values().get(
      spreadsheetId = ss_id,
      range=a1_range
    ).execute()

    return values['values']


#-------------------------------------------------------------------------------
def hide_rows(sheets_api, ss_id, start, end):
    '''
    @start: inclusive row
    @end: inclusive row
    '''
    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId = ss_id,
        body = {
            'requests': {
                'updateDimensionProperties': {
                    'fields': '*',
                    'range': {
                        'startIndex': start-1,
                        'endIndex': end,
                        'dimension': 'ROWS'
                    },
                    'properties': {
                        'hiddenByUser': True
                    }
                }
            }
        }
    ).execute()



#-------------------------------------------------------------------------------
if __name__ == "__main__":
    route_id = "it03f21l553"
    title = "TEST"

    drive_api = auth_gservice('drive')
    sheet_id = create_sheet(drive_api, title)

    sheets_api = auth_gservice('sheets')
    write_sheet(sheets_api, sheet_id, route_id)

