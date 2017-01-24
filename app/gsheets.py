'''app.gsheets'''
import httplib2, json, logging, requests
from datetime import datetime
from dateutil.parser import parse
from oauth2client.client import SignedJwtAssertionCredentials
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
log = logging.getLogger(__name__)

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
        log.error('Error authorizing %s: %s', name, str(e))
        return False

    log.debug('Sheets service authorized')

    return service

#-------------------------------------------------------------------------------
def get_prop(service, ss_id):
    try:
        prop = service.spreadsheets().get(
            spreadsheetId = ss_id
        ).execute()
    except Exception as e:
        log.error('couldnt get ss prop: %s', str(e))
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
        log.error('Error writing to sheet: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def append_row(service, ss_id, wks, row):
    prop = get_prop(service, ss_id)
    max_rows = prop['gridProperties']['rowCount']
    row_range = '%s!%s:%s' % (wks, max_rows+1,max_rows+1)
    write_rows(service, ss_id, [row], row_range)

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
        log.error('Error writing to sheet: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def get_values(service, ss_id, a1_range):
    try:
        result = service.spreadsheets().values().get(
          spreadsheetId = ss_id,
          range=a1_range
        ).execute()
    except Exception as e:
        log.error('Error getting values from sheet: %s', str(e))
        return False

    return result.get('values', [])

#-------------------------------------------------------------------------------
def get_row(service, ss_id, wks, row):
    a1 = '%s!%s:%s' % (wks, str(row),str(row))
    return get_values(service, ss_id, a1)[0]

#-------------------------------------------------------------------------------
def insert_rows_above(service, ss_id, row, num):
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId = ss_id,
            body = {
                "requests": {
                    "insertDimension": {
                        "range": {
                            "sheetId": 0,
                            "dimension": "ROWS",
                            "startIndex": row-1,
                            "endIndex": row-1+num
                        },
                        "inheritFromBefore": False
                    }
                }
            }
        ).execute()
    except Exception as e:
        log.error('Error inserting rows: ' + str(e))
        return False

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
        log.error('Error hiding rows: %s', str(e))
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
        log.error('Error formatting cells: %s', str(e))
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

    log.debug(json.dumps(cells))

    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId = ss_id,
            body = {
                "requests": _requests
            }).execute()
    except Exception as e:
        log.error('Error bolding cells: %s', str(e))
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

#-------------------------------------------------------------------------------
def a1(row, col):
    letter = col_idx_to_a1(col-1)
    return '%s%s' % (letter,(row))
