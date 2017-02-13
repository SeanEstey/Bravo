'''app.gsheets'''
import httplib2, json, logging, requests
from datetime import datetime
from dateutil.parser import parse
from oauth2client.service_account import ServiceAccountCredentials
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
from app import get_logger
log = get_logger('gsheets')

#-------------------------------------------------------------------------------
def update_cell(service, ss_id, range_, value):
    api_ss_values_update(service, ss_id, range_, [[value]])

#-------------------------------------------------------------------------------
def get_row(service, ss_id, wks, row):
    range_ = '%s!%s:%s' % (wks, str(row),str(row))
    return api_ss_values_get(service, ss_id, range_)[0]

#-------------------------------------------------------------------------------
def get_range(service, ss_id, wks, range_):
    return api_ss_values_get(service, ss_id, '%s!%s' %(wks,range_))

#-------------------------------------------------------------------------------
def append_row(service, ss_id, sheet_title, values):
    sheet = api_ss_get(service, ss_id, sheet_title=sheet_title)

    max_rows = sheet['gridProperties']['rowCount']
    range_ = '%s!%s:%s' % (sheet_title, max_rows+1,max_rows+1)

    api_ss_values_append(service, ss_id, range_, [values])

#-------------------------------------------------------------------------------
def write_rows(service, ss_id, range_, values):
    api_ss_values_update(service, ss_id, range_, values)

#-------------------------------------------------------------------------------
def insert_rows_above(service, ss_id, row, num):
    range_ = {
        "sheetId": 0,
        "dimension": "ROWS",
        "startIndex": row-1,
        "endIndex": row-1+num}
    api_ss_batch_update(service, ss_id, 'insertDimension', range_=range_)

#-------------------------------------------------------------------------------
def hide_rows(service, ss_id, start, end):
    '''
    @start: inclusive row
    @end: inclusive row
    '''

    fields = '*'
    range_ = {
        'startIndex': start-1,
        'endIndex': end,
        'dimension': 'ROWS'}
    properties = {
        'hiddenByUser': True}

    api_ss_batch_update(service, ss_id, 'updateDimensionProperties',
        fields=fields, range_=range_, properties=properties)

#-------------------------------------------------------------------------------
def vert_align_cells(service, ss_id, start_row, end_row, start_col, end_col):
    '''
    '''

    range_ = {
        "sheetId": 0,
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
def bold_cells(service, ss_id, cells):
    '''
    @cells: list of [ [row,col], [row,col] ]
    '''

    # range startIndex: inclusive, endIndex: exclusive

    requests_=[]

    for cell in cells:
        range_ = {
            "sheetId": 0,
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
def gauth(oauth):
    name = 'sheets'
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    version = 'v4'

    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            oauth,
            scopes=scope)
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build(name, version, http=http, cache_discovery=False)
    except Exception as e:
        log.error('error authorizing %s: %s', name, str(e))
        return False

    log.debug('sheets service authorized')

    return service

'''API Calls'''

#-------------------------------------------------------------------------------
def api_ss_get(service, ss_id, sheet_title=None):
    '''
	Returns: spreadsheet property: {
	  "spreadsheetId": string,
	  "properties": {
		object(SpreadsheetProperties)
	  },
	  "sheets": [
		{
		  object(Sheet)
		}
	  ],
	  "namedRanges": [
		{
		  object(NamedRange)
		}
	  ],
	}
    '''
    try:
        ss = service.spreadsheets().get(spreadsheetId=ss_id).execute()
    except Exception as e:
        log.error('couldnt get ss prop: %s', str(e))
        return False

    if not sheet_title:
        return ss

    for sheet in ss['sheets']:
        if sheet['properties']['title'] == sheet_title:
            return sheet['properties']

#-------------------------------------------------------------------------------
def api_ss_values_get(service, ss_id, range_):
    '''https://developers.google.com/resources/api-libraries/documentation/\
    sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#get
    '''

    try:
        result = service.spreadsheets().values().get(
          spreadsheetId = ss_id,
          range=range_
        ).execute()
    except Exception as e:
        log.error('Error getting values from sheet: %s', str(e))
        log.debug('', exc_info=True)
        raise

    return result.get('values', [])

#-------------------------------------------------------------------------------
def api_ss_values_update(service, ss_id, range_, values):
    '''https://developers.google.com/resources/api-libraries/documentation/\
    sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#update
    '''

    call = service.spreadsheets().values().update
    body = {
        "values": values,
        "majorDimension": "ROWS"}
    input_ = 'USER_ENTERED'

    try:
        call(spreadsheetId=ss_id, valueInputOption=input_, range=range_, body=body).execute()
    except Exception as e:
        log.error('Error updating sheet: %s', str(e))
        log.debug('', exc_info=True)
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
        log.debug('', exc_info=True)
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


