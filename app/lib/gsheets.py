# app.lib.gsheets

"""Wrapper methods for working with Google Sheets API v4.

Sheets v4 docs:
    https://goo.gl/y5pysQ
spreadsheets pydocs:
    https://goo.gl/iZbKk5
apiclient docs:
    https://google.github.io/google-api-python-client/docs/epy/googleapiclient-module.html
"""

import logging
import gc
from googleapiclient.errors import HttpError
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def gauth(keyfile_dict):
    '''Returns 'spreadsheets' Resource object (documentation: goo.gl/Jy2cwP)
    '''

    from .gservice_acct import auth
    return auth(
        keyfile_dict,
        name='sheets',
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
        version='v4')

#-------------------------------------------------------------------------------
def num_columns(service, ss_id, wks):

    ss = _ss_get(service, ss_id)
    for sheet in ss['sheets']:
        if sheet['properties']['title'] == wks:
            return sheet['properties']['gridProperties']['columnCount']

#-------------------------------------------------------------------------------
def num_rows(service, ss_id, wks):

    ss = _ss_get(service, ss_id)
    for sheet in ss['sheets']:
        if sheet['properties']['title'] == wks:
            return sheet['properties']['gridProperties']['rowCount']

#-------------------------------------------------------------------------------
def get_row(service, ss_id, wks, row):

    return _ss_values_get(
        service,
        ss_id,
        wks,
        '%s:%s'%(str(row),str(row))
    )['values'][0]

#-------------------------------------------------------------------------------
def get_headers(service, ss_id, wks):

    return get_row(service, ss_id, wks, 1)

#-------------------------------------------------------------------------------
def get_header_column(oauth, ss_id, wks, col_name):

    service = gauth(oauth)
    hdr = get_headers(service, ss_id, wks)
    col = hdr.index(col_name)+1
    service = None
    gc.collect()
    return col

#-------------------------------------------------------------------------------
def get_values(service, ss_id, wks, range_):

    return _ss_values_get(service, ss_id, wks, range_)['values']

#-------------------------------------------------------------------------------
def write_cell(oauth, ss_id, wks, row, col_name, value):
    '''Create service and write cell from column name'''

    service = gauth(oauth)
    hdr = get_headers(service, ss_id, wks)
    range_ = to_range(row, hdr.index(col_name)+1)
    _ss_values_update(service, ss_id, wks, range_, [[value]])
    service = None
    gc.collect()

#-------------------------------------------------------------------------------
def update_cell(service, ss_id, wks, range_, value):

    _ss_values_update(service, ss_id, wks, range_, [[value]])

#-------------------------------------------------------------------------------
def append_row(service, ss_id, wks_title, values):

    n_rows = _ss_get(service, ss_id, wks_title=wks_title)['gridProperties']['rowCount']
    _ss_values_append(
        service,
        ss_id,
        wks_title,
        '%s:%s' % (n_rows+1, n_rows+1),
        [values]
    )

#-------------------------------------------------------------------------------
def write_rows(service, ss_id, wks, range_, values):
    '''Write rows to given range. Will append new rows if range exceeds
    grid size'''

    _ss_values_update(service, ss_id, wks, range_, values)

#-------------------------------------------------------------------------------
def insert_rows_above(service, ss_id, wks_id, row, num):

    _ss_batch_update(
        service, ss_id, 'insertDimension',
        range_ = {
            "sheetId": wks_id,
            "dimension": "ROWS",
            "startIndex": row-1,
            "endIndex": row-1+num
        }
    )

#-------------------------------------------------------------------------------
def hide_rows(service, ss_id, wks_id, start, end):
    '''@start: inclusive row
       @end: inclusive row
    '''

    _ss_batch_update(
        service, ss_id, 'updateDimensionProperties',
        fields= '*',
        range_= {
            'sheetId': wks_id,
            'startIndex': start-1,
            'endIndex': end,
            'dimension': 'ROWS'
        },
        properties= {
            'hiddenByUser': True
        }
    )

#-------------------------------------------------------------------------------
def vert_align_cells(service, ss_id, wks_id, start_row, end_row, start_col, end_col):

    _ss_batch_update(
        service, ss_id, 'repeatCell',
        cell= {
            "userEnteredFormat": {
                "verticalAlignment" : "MIDDLE"
            }
        },
        range_={
            "sheetId": wks_id,
            "startRowIndex": start_row-1,
            "endRowIndex": end_row-1,
            "startColumnIndex": start_col-1
        },
        fields= 'userEnteredFormat(verticalAlignment)'
    )

#-------------------------------------------------------------------------------
def bold_cells(service, ss_id, wks_id, cells):
    '''@cells: list of [ [row,col], [row,col] ]
    '''

    actions=[]

    for cell in cells:
        actions.append(
            _ss_batch_update(
                service, ss_id, 'repeatCell',
                range_= {
                    "sheetId": wks_id,
                    "startRowIndex": cell[0]-1,
                    "endRowIndex": cell[0],
                    "startColumnIndex": cell[1]-1, # Inclusive
                    "endColumnIndex": cell[1] # Exclusive
                },
                cell= {
                    "userEnteredFormat": {
                        "textFormat": {
                            "bold": True
                        }
                    }
                },
                fields='userEnteredFormat(textFormat)',
                execute=False
            )
        )

    _execute(service, ss_id, actions)

#-------------------------------------------------------------------------------
def to_range(row, col):

    letter = col_idx_to_a1(col-1)
    return '%s%s' % (letter,str(row))

#-------------------------------------------------------------------------------
def col_idx_to_a1(idx):

    alphabet = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z']

    if idx < len(alphabet):
        return alphabet[idx]
    elif idx < len(alphabet)*2:
        # AA, AB, AC, etc
        return "A%s" % alphabet[idx - len(alphabet)]
    else:
        log.error('not implemented converting to range for wide idx of %s', idx)
        return False


#-------------------------------------------------------------------------------
def handleHttpError(e):

    import json, time

    if e.resp.get('content-type', '').startswith('application/json'):
        reason = json.loads(e.content)
        #log.error('HttpError. Reason=%s', reason)

    #log.error('HttpError code=%s', e.resp.status)

    if e.resp.status in [403, 500, 503]:
        log.error('HttpError: Sheets service unavailable. Sleeping 5s...')
        time.sleep(5)
        raise
    elif e.resp.status == 429:
        log.error('HttpError: Insufficient tokens for quota. Sleeping 75s...')
        time.sleep(75)
        raise
    else:
        log.error('HttpError code=%s. Raising...', e.resp.status)
        raise


'''API Calls'''

#-------------------------------------------------------------------------------
def _ss_get(service, ss_id, wks_title=None):
    '''Returns <Spreadsheet> dict (does not contain values)

    Spreadsheet = {
      "spreadsheetId": string,
      "properties": {
        <SpreadsheetProperties>
	   },
	   "sheets": [
         <Sheet>
	  ],
	  "namedRanges": [
        <NamedRange>
	  ],
      ...
	}

    Sheet = {
      "properties": {
        "title": <str>,
        "gridProperties": {
            "columnCount": <int>,
            "rowCount": <int>,
        },
        ...
      }
    }'''

    ss = None

    try:
        ss = service.spreadsheets().get(spreadsheetId=ss_id).execute(num_retries=3)
    except HttpError as e:
        handleHttpError(e)

    if not wks_title:
        return ss

    for sheet in ss['sheets']:
        if sheet['properties']['title'] == wks_title:
            return sheet['properties']

#-------------------------------------------------------------------------------
def _ss_values_get(service, ss_id, wks, range_):
    '''Returns <ValuesRange>:
	{
      "range": string,
      "majorDimension": enum(Dimension),
        "values": [
          array
        ],
    }

    pydocs:
    https://developers.google.com/resources/api-libraries/documentation/sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#get
    '''

    try:
        result = service.spreadsheets().values().get(
          spreadsheetId= ss_id,
          range='%s!%s'%(wks,range_)
        ).execute(num_retries=3)
    except Exception as e:
        log.error('Error getting SS values from %s', wks)
        raise

    return result

#-------------------------------------------------------------------------------
def _ss_values_update(service, ss_id, wks, range_, values):
    '''
    (shift-select url w/ mouse, right-click copy)
    https://developers.google.com/resources/api-libraries/documentation/sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#update
    update() returns a HTTPRequest. execute() runs it
    '''

    try:
        request = service.spreadsheets().values().update(
            spreadsheetId=ss_id,
            valueInputOption='USER_ENTERED',
            range='%s!%s' % (wks, range_),
            body={
                "values": values,
                "majorDimension": "ROWS"
            }
        )
        request.execute(num_retries=3)
    except HttpError as e:
        log.error('Error updating %s sheet. Invalid data.', wks,
            extra={'request':request.to_json(), 'exc_msg':e.message, 'exc_args':e.args})
        raise
    except Exception as e:
        log.exception('Exception updating %s sheet', wks, extra={'dump':vars(e)})
        raise

#-------------------------------------------------------------------------------
def _ss_values_append(service, ss_id, wks, range_, values):
    '''https://developers.google.com/resources/api-libraries/documentation/\
    sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#append
    '''

    try:
        service.spreadsheets().values().append(
            spreadsheetId= ss_id,
            valueInputOption= 'USER_ENTERED',
            range= '%s!%s' % (wks, range_),
            body = {
                "values": values,
                "majorDimension": "ROWS"
            }
        ).execute(num_retries=3)
    except Exception as e:
        log.error('Error appending to sheet: %s', e.message)
        raise

#-------------------------------------------------------------------------------
def _execute(service, ss_id, actions):
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId = ss_id,
            body = {
                "requests": actions
            }).execute(num_retries=3)
    except Exception as e:
        log.error('Error executing batch update: %s', e.message, extra={'requests':actions})
        raise

#-------------------------------------------------------------------------------
def _ss_batch_update(service, ss_id, request, range_=None, cell=None, fields=None, properties=None, execute=True):
    '''https://developers.google.com/resources/api-libraries/documentation/\
    sheets/v4/python/latest/sheets_v4.spreadsheets.html#batchUpdate
    '''

    actions = []

    if request == 'insertDimension':
        actions.append({
            'insertDimension': {
                "range": range_,
                "inheritFromBefore": False
            }
        })
    elif request == 'updateDimensionProperties':
        actions.append({
            'updateDimensionProperties': {
                'fields': fields,
                'range': range_,
                'properties': properties
            }
        })
    elif request == 'repeatCell':
        actions.append({
            'repeatCell': {
                'fields': fields,
                'range': range_,
                'cell': cell
            }
        })

    if not execute:
        return actions

    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId = ss_id,
            body = {"requests": actions}
        ).execute(num_retries=3)
    except HTTPError as e:
        log.error('Error batch updating %s worksheet: %s', str(e.reason),
            extra={'code':e.code, 'reason':str(e.reason)})
        raise
    except Exception as e:
        log.error('Error performing batch update: %s', e.message, extra={'requests':actions})
        raise

    '''Requests resource: {
	  // Union field kind can be only one of the following:
	  "updateSpreadsheetProperties": {
		object(UpdateSpreadsheetPropertiesRequest)
	  },
	  "updateSheetProperties": {
		object(UpdateSheetPropertiesRequest)
	  },
	  "updateDimensionProperties": {
		object(UpdateDimensionPropertiesRequest)
	  },
	  "updateNamedRange": {
		object(UpdateNamedRangeRequest)
	  },
	  "repeatCell": {
		object(RepeatCellRequest)
	  },
	  "addNamedRange": {
		object(AddNamedRangeRequest)
	  },
	  "deleteNamedRange": {
		object(DeleteNamedRangeRequest)
	  },
	  "addSheet": {
		object(AddSheetRequest)
	  },
	  "deleteSheet": {
		object(DeleteSheetRequest)
	  },
	  "autoFill": {
		object(AutoFillRequest)
	  },
	  "cutPaste": {
		object(CutPasteRequest)
	  },
	  "copyPaste": {
		object(CopyPasteRequest)
	  },
	  "mergeCells": {
		object(MergeCellsRequest)
	  },
	  "unmergeCells": {
		object(UnmergeCellsRequest)
	  },
	  "updateBorders": {
		object(UpdateBordersRequest)
	  },
	  "updateCells": {
		object(UpdateCellsRequest)
	  },
	  "addFilterView": {
		object(AddFilterViewRequest)
	  },
	  "appendCells": {
		object(AppendCellsRequest)
	  },
	  "clearBasicFilter": {
		object(ClearBasicFilterRequest)
	  },
	  "deleteDimension": {
		object(DeleteDimensionRequest)
	  },
	  "deleteEmbeddedObject": {
		object(DeleteEmbeddedObjectRequest)
	  },
	  "deleteFilterView": {
		object(DeleteFilterViewRequest)
	  },
	  "duplicateFilterView": {
		object(DuplicateFilterViewRequest)
	  },
	  "duplicateSheet": {
		object(DuplicateSheetRequest)
	  },
	  "findReplace": {
		object(FindReplaceRequest)
	  },
	  "insertDimension": {
		object(InsertDimensionRequest)
	  },
	  "moveDimension": {
		object(MoveDimensionRequest)
	  },
	  "updateEmbeddedObjectPosition": {
		object(UpdateEmbeddedObjectPositionRequest)
	  },
	  "pasteData": {
		object(PasteDataRequest)
	  },
	  "textToColumns": {
		object(TextToColumnsRequest)
	  },
	  "updateFilterView": {
		object(UpdateFilterViewRequest)
	  },
	  "appendDimension": {
		object(AppendDimensionRequest)
	  },
	  "addConditionalFormatRule": {
		object(AddConditionalFormatRuleRequest)
	  },
	  "updateConditionalFormatRule": {
		object(UpdateConditionalFormatRuleRequest)
	  },
	  "deleteConditionalFormatRule": {
		object(DeleteConditionalFormatRuleRequest)
	  },
	  "sortRange": {
		object(SortRangeRequest)
	  },
	  "setDataValidation": {
		object(SetDataValidationRequest)
	  },
	  "setBasicFilter": {
		object(SetBasicFilterRequest)
	  },
	  "addProtectedRange": {
		object(AddProtectedRangeRequest)
	  },
	  "updateProtectedRange": {
		object(UpdateProtectedRangeRequest)
	  },
	  "deleteProtectedRange": {
		object(DeleteProtectedRangeRequest)
	  },
	  "autoResizeDimensions": {
		object(AutoResizeDimensionsRequest)
	  },
	  "addChart": {
		object(AddChartRequest)
	  },
	  "updateChartSpec": {
		object(UpdateChartSpecRequest)
	  },
	  "updateBanding": {
		object(UpdateBandingRequest)
	  },
	  "addBanding": {
		object(AddBandingRequest)
	  },
	  "deleteBanding": {
		object(DeleteBandingRequest)
	  },
	  // End of list of possible types for union field kind.
	}
	'''
    pass
