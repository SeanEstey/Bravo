'''app.gsheets'''

import json
import gspread
import requests
from datetime import datetime
from dateutil.parser import parse
import logging
from flask import current_app

# Google
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest

from . import db
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def gauth(oauth):
    name = 'sheets'
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    version = 'v4'

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

    logger.debug('Sheets service authorized')

    return service

#-------------------------------------------------------------------------------
def get_prop(service, ss_id):
    try:
        prop = service.spreadsheets().get(
            spreadsheetId = ss_id
        ).execute()
    except Exception as e:
        logger.error('couldnt get ss prop: %s', str(e))
        return False

    return prop['properties']

#-------------------------------------------------------------------------------
def write_rows(service, ss_id, rows, a1_range):
    '''Write data to sheet
    Returns: UpdateValuesResponse
    https://developers.google.com/sheets/reference/rest/v4/UpdateValuesResponse
    '''

    try:
        service.spreadsheets().values().update(
          spreadsheetId = ss_id,
          valueInputOption = "USER_ENTERED",
          range = a1_range,
          body = {
            "majorDimension": "ROWS",
            "values": rows
          }
        ).execute()
    except Exception as e:
        logger.error('Error writing to sheet: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def update_cell(service, ss_id, a1_range, value):
    '''Write data to sheet
    @a1_range: cell range i.e. "Routes!D65"
    Returns: UpdateValuesResponse
    https://developers.google.com/sheets/reference/rest/v4/UpdateValuesResponse
    '''

    try:
        service.spreadsheets().values().update(
          spreadsheetId = ss_id,
          valueInputOption = "USER_ENTERED",
          range = a1_range,
          body = {
            "majorDimension": "ROWS",
            "values": [[value]]
          }
        ).execute()
    except Exception as e:
        logger.error('Error writing to sheet: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def get_values(service, ss_id, a1_range):
    try:
        result = service.spreadsheets().values().get(
          spreadsheetId = ss_id,
          range=a1_range
        ).execute()
    except Exception as e:
        logger.error('Error getting values from sheet: %s', str(e))
        return False

    return result.get('values', [])

#-------------------------------------------------------------------------------
def hide_rows(service, ss_id, start, end):
    '''
    @start: inclusive row
    @end: inclusive row
    '''
    try:
        service.spreadsheets().batchUpdate(
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
    except Exception as e:
        logger.error('Error hiding rows: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def vert_align_cells(service, ss_id, start_row, end_row, start_col, end_col):
    '''
    RepeatCell ref: https://developers.google.com/sheets/reference/rest/v4/spreadsheets/request#repeatcellrequest
    VerticalAlignment ref: https://developers.google.com/sheets/reference/rest/v4/spreadsheets#verticalalign
    '''

    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId = ss_id,
            body = {
                "requests": [{
                  "repeatCell": {
                    "range": {
                      "sheetId": 0,
                      "startRowIndex": start_row-1,
                      "endRowIndex": end_row-1,
                      "startColumnIndex": start_col-1
                    },
                    "cell": {
                      "userEnteredFormat": {
                        "verticalAlignment" : "MIDDLE"
                      }
                    },
                    "fields": "userEnteredFormat(verticalAlignment)"
                  }
                }]
            }).execute()
    except Exception as e:
        logger.error('Error formatting cells: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def bold_cells(service, ss_id, cells):
    '''
    @cells: list of [ [row,col], [row,col] ]
    '''
    _requests = []

    # startIndex: inclusive, endIndex: exclusive

    for cell in cells:
        _requests.append({
          "repeatCell": {
            "range": {
              "sheetId": 0,
              "startRowIndex": cell[0]-1,
              "endRowIndex": cell[0],
              "startColumnIndex": cell[1]-1,
              "endColumnIndex": cell[1]
            },
            "cell": {
              "userEnteredFormat": {
                "textFormat": {
                  "bold": True
                }
              }
            },
            "fields": "userEnteredFormat(textFormat)"
          }
        })

    logger.debug(json.dumps(cells))

    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId = ss_id,
            body = {
                "requests": _requests
            }).execute()
    except Exception as e:
        logger.error('Error bolding cells: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def col_idx_to_a1(idx):
    alphabet = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z']

    if idx < len(alphabet):
        return alphabet[idx]

    # TODO: expand this if necessary for wide sheets w/ columns like AA, AB, etc
    '''
    parts = str(round(float(idx/len(alphabet)),1)).split('.')

    if int(parts[0]) < len(alphabet):
        return alphabet[int(parts[1])]

    col_size = int(parts[0])
    for i in range(int(parts[0])):
        a1 += alphabet[i]
    '''

# ----- GSPREAD (OLD) --------------------------------------------------------


#-------------------------------------------------------------------------------
def auth(oauth, scope):
    '''python gspread
    @scope: array of Google service URL's to authorize
    '''

    try:
      credentials = SignedJwtAssertionCredentials(
        oauth['client_email'],
        oauth['private_key'],
        scope
      )

      return gspread.authorize(credentials)

    except Exception as e:
        logger.info('gsheets.auth():', exc_info=True)
        return False

#-------------------------------------------------------------------------------
def update_entry(agency, status, destination):
    '''Updates the 'Email Status' column in a worksheet
    destination: dict containing 'sheet', 'worksheet', 'row', 'upload_status'
    '''

    try:
        oauth = db['agencies'].find_one({'name':agency})['google']['oauth']
        gc = auth(oauth, ['https://spreadsheets.google.com/feeds'])
        sheet = gc.open(current_app.config['GSHEET_NAME'])
        wks = sheet.worksheet(destination['worksheet'])
    except Exception as e:
        logger.error(
          'Error opening worksheet %s: %s' ,
          destination['worksheet'], str(e)
        )
        return False

    headers = wks.row_values(1)

    # Make sure the row entry still exists in the worksheet
    # and hasn't been replaced by other data or deleted
    cell = wks.cell(destination['row'], headers.index('Upload Status')+1)

    if not cell:
        logger.error('update_entry cell not found')
        return False

    if str(cell.value) == destination['upload_status']:
        try:
            wks.update_cell(
              destination['row'],
              headers.index('Email Status')+1,
              status
            )
        except Exception as e:
            logger.error(
              'Error writing to worksheet %s: %s',
              destination['worksheet'], str(e)
            )
            return False

    return True

    # Create RFU if event is dropped/bounced and is from a collection receipt
    '''
    if destination['worksheet'] == 'Routes':
        if destination['status'] == 'dropped' or destination['status'] == 'bounced':
            wks = sheet.worksheet('RFU')
            headers = wks.row_values(1)

            rfu = [''] * len(headers)
            rfu[headers.index('Request Note')] = \
                'Email ' + db_record['recipient'] + ' dropped.'

            if 'account_number' in db_record:
              rfu[headers.index('Account Number')] = db_record['account_number']

            logger.info(
              'Creating RFU for bounced/dropped email %s', json.dumps(rfu)
            )

            try:
                wks.current_append_row(rfu)
            except Exception as e:
                logger.error('Error writing to RFU worksheet: %s', str(e))
                return False
    '''

#-------------------------------------------------------------------------------
def create_rfu(agency, note,
               a_id=None, npu=None, block=None, _date=None, name_addy=None,
               driver_notes=None, office_notes=None):

    try:
        oauth = db['agencies'].find_one({'name':agency})['google']['oauth']
        gc = auth(oauth, ['https://spreadsheets.google.com/feeds'])
        sheet = gc.open(current_app.config['GSHEET_NAME'])
        wks = sheet.worksheet('RFU')
    except Exception as e:
        logger.error('Could not open RFU worksheet: %s', str(e))
        return False

    headers = wks.row_values(1)

    rfu = [''] * len(headers)

    rfu[headers.index('Request Note')] = note

    if a_id != None:
        rfu[headers.index('Account Number')] = a_id

    if npu != None:
        rfu[headers.index('Next Pickup Date')] = npu

    if block != None:
        rfu[headers.index('Block')] = block

    if _date != None:
        rfu[headers.index('Date')] = _date

    if name_addy != None:
        rfu[headers.index('Name & Address')] = name_addy

    if driver_notes is not None:
        rfu[headers.index('Driver Notes')] = driver_notes

    if office_notes is not None:
        rfu[headers.index('Office Notes')] = office_notes

    logger.debug('Creating RFU: ' + json.dumps([item for item in rfu if item]))

    try:
        wks.append_row(rfu)
    except Exception as e:
        logger.error('Could not write to RFU sheet: %s', str(e))
        return False

    return True
