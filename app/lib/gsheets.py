'''app.lib.gsheets'''
import httplib2, json, logging, requests
from datetime import datetime
from dateutil.parser import parse
from oauth2client.service_account import ServiceAccountCredentials
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
from app.lib.loggy import Loggy
log = Loggy('gsheets')

#-------------------------------------------------------------------------------
def num_columns(service, ss_id, wks):
    ss_info = api_ss_get(service, ss_id)
    for sheet in ss_info['sheets']:
        if sheet['properties']['title'] == wks:
            return sheet['properties']['gridProperties']['columnCount']

#-------------------------------------------------------------------------------
def num_rows(service, ss_id, wks):
    ss_info = api_ss_get(service, ss_id)
    for sheet in ss_info['sheets']:
        if sheet['properties']['title'] == wks:
            return sheet['properties']['gridProperties']['rowCount']

#-------------------------------------------------------------------------------
def get_row(service, ss_id, wks, row):
    return api_ss_values_get(
        service,
        ss_id,
        wks,
        '%s:%s'%(str(row),str(row))
    )['values'][0]

#-------------------------------------------------------------------------------
def get_values(service, ss_id, wks, range_):
    return api_ss_values_get(service, ss_id, wks, range_)['values']

#-------------------------------------------------------------------------------
def update_cell(service, ss_id, wks, range_, value):
    api_ss_values_update(service, ss_id, wks, range_, [[value]])

#-------------------------------------------------------------------------------
def append_row(service, ss_id, wks_title, values):
    sheet = api_ss_get(service, ss_id, wks_title=wks_title)
    max_rows = sheet['gridProperties']['rowCount']
    range_ = '%s!%s:%s' % (wks_title, max_rows+1,max_rows+1)
    api_ss_values_append(service, ss_id, range_, [values])

#-------------------------------------------------------------------------------
def write_rows(service, ss_id, wks, range_, values):
    '''Write rows to given range. Will append new rows if range exceeds
    grid size
    '''
    api_ss_values_update(service, ss_id, wks, range_, values)

#-------------------------------------------------------------------------------
def insert_rows_above(service, ss_id, wks_id, row, num):
    range_ = {
        "sheetId": wks_id,
        "dimension": "ROWS",
        "startIndex": row-1,
        "endIndex": row-1+num}
    api_ss_batch_update(service, ss_id, 'insertDimension', range_=range_)

#-------------------------------------------------------------------------------
def hide_rows(service, ss_id, wks_id, start, end):
    '''@start: inclusive row
       @end: inclusive row
    '''
    fields = '*'
    range_ = {
        'sheetId': wks_id,
        'startIndex': start-1,
        'endIndex': end,
        'dimension': 'ROWS'}
    properties = {
        'hiddenByUser': True}

    api_ss_batch_update(service, ss_id, 'updateDimensionProperties',
        fields=fields, range_=range_, properties=properties)

#-------------------------------------------------------------------------------
def vert_align_cells(service, ss_id, wks_id, start_row, end_row, start_col, end_col):
    range_ = {
        "sheetId": wks_id,
        "startRowIndex": start_row-1,
        "endRowIndex": end_row-1,
        "startColumnIndex": start_col-1}
    cell = {
        "userEnteredFormat": {
            "verticalAlignment" : "MIDDLE"}}
    fields = 'userEnteredFormat(verticalAlignment)'

    api_ss_batch_update(service, ss_id, 'repeatCell',
        cell=cell, range_=range_, fields=fields)

#-------------------------------------------------------------------------------
def bold_cells(service, ss_id, wks_id, cells):
    '''@cells: list of [ [row,col], [row,col] ]
    '''

    # range startIndex: inclusive, endIndex: exclusive

    requests_=[]

    for cell in cells:
        range_ = {
            "sheetId": wks_id,
            "startRowIndex": cell[0]-1,
            "endRowIndex": cell[0],
            "startColumnIndex": cell[1]-1,
            "endColumnIndex": cell[1]}
        cell = {
            "userEnteredFormat": {
                "textFormat": {
                    "bold": True}}}
        fields = 'userEnteredFormat(textFormat)'

        requests_.append(api_ss_batch_update(
            service, ss_id, 'repeatCell',
            range_=range_, cell=cell, fields=fields, execute=False))
    api_execute(service, ss_id, requests_)

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
def gauth(oauth):
    name = 'sheets'
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    version = 'v4'

    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            oauth,
            scopes=scope)
        http = httplib2.Http(cache=".cache")
        http = credentials.authorize(http)
        service = build(name, version, http=http, cache_discovery=True)
    except Exception as e:
        log.error('error authorizing %s: %s', name, str(e))
        return False

    #log.debug('sheets service authorized')

    http = None
    credentials = None
    return service

'''API Calls'''

#-------------------------------------------------------------------------------
def api_ss_get(service, ss_id, wks_title=None):
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

    try:
        ss = service.spreadsheets().get(spreadsheetId=ss_id).execute()
    except Exception as e:
        log.error('couldnt get ss prop: %s', str(e))
        return False

    if not wks_title:
        return ss

    for sheet in ss['sheets']:
        if sheet['properties']['title'] == wks_title:
            return sheet['properties']

#-------------------------------------------------------------------------------
def api_ss_values_get(service, ss_id, wks, range_):
    '''Returns <ValuesRange>:
	{
      "range": string,
      "majorDimension": enum(Dimension),
        "values": [
          array
        ],
    }

    pydocs: https://developers.google.com/resources/api-libraries/documentation/\
    sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#get
    '''

    try:
        result = service.spreadsheets().values().get(
          spreadsheetId = ss_id,
          range='%s!%s'%(wks,range_)
        ).execute()
    except Exception as e:
        log.error('Error getting values from sheet: %s', str(e))
        log.debug(str(e))
        raise

    return result

#-------------------------------------------------------------------------------
def api_ss_values_update(service, ss_id, wks, range_, values):
    '''https://developers.google.com/resources/api-libraries/documentation/\
    sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#update
    '''

    call = service.spreadsheets().values().update
    body = {
        "values": values,
        "majorDimension": "ROWS"}
    input_ = 'USER_ENTERED'

    try:
        call(
            spreadsheetId=ss_id,
            valueInputOption=input_,
            range='%s!%s'%(wks,range_),
            body=body).execute()
    except Exception as e:
        log.error('Error updating sheet: %s', str(e))
        log.debug(str(e))
        return False

#-------------------------------------------------------------------------------
def api_ss_values_append(service, ss_id, range_, values):
    '''https://developers.google.com/resources/api-libraries/documentation/\
    sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#append
    '''

    call = service.spreadsheets().values().append
    body = {
        "values": values,
        "majorDimension": "ROWS"}
    input_ = 'USER_ENTERED'

    try:
        call(spreadsheetId=ss_id, valueInputOption=input_, range=range_, body=body).execute()
    except Exception as e:
        log.error('Error appending to sheet: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def api_execute(service, ss_id, requests):
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId = ss_id,
            body = {
                "requests": requests
            }).execute()
    except Exception as e:
        log.error('error executing batch update. desc=%s', str(e))
        log.debug(str(e))
        raise

#-------------------------------------------------------------------------------
def api_ss_batch_update(service, ss_id, request, range_=None, cell=None, fields=None, properties=None, execute=True):
    '''https://developers.google.com/resources/api-libraries/documentation/\
    sheets/v4/python/latest/sheets_v4.spreadsheets.html#batchUpdate
    '''

    requests = []

    if request == 'insertDimension':
        requests.append({
            'insertDimension': {
                "range": range_,
                "inheritFromBefore": False}})
    elif request == 'updateDimensionProperties':
        requests.append({
            'updateDimensionProperties': {
                'fields': fields,
                'range': range_,
                'properties': properties}})
    elif request == 'repeatCell':
        requests.append({
            'repeatCell': {
                'fields': fields,
                'range': range_,
                'cell': cell}})

    if not execute:
        return requests

    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId = ss_id,
            body = {
                "requests": requests
            }).execute()
    except Exception as e:
        log.error('error doing batch update request=%s. desc=%s', request, str(e))
        return False

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
