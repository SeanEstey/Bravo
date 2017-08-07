# app.lib.gsheets_cls

import gc, logging, re
from app import get_keys
from .timer import Timer
from .gsheets import to_range, _ss_get, _ss_values_get, _ss_values_update
from .gsheets import handleHttpError, _ss_values_append, _execute, _ss_batch_update
from .gservice_acct import auth
from googleapiclient.errors import HttpError

log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
class SS():

    service = None
    ss_id = None
    ssObj = None # Spreadsheet
    propObj = None # SpreadsheetProperties

    #---------------------------------------------------------------
    def wks(self, name):

        for sheet in self.ssObj['sheets']:
            if sheet['properties']['title'] == name:
                return Wks(self.service, self.ss_id, sheet)
                break

    #---------------------------------------------------------------
    def _get_resource(self, n=0):

        max_retries = 3

        if n >= max_retries:
            log.error('Exceeded max attempts to acquire SS resource.')
            raise Exception('Failed to acquire SS resource.')

        #log.debug('Acquiring SS resource. n=%s', n)

        try:
            self.ssObj = self.service.spreadsheets().get(
                spreadsheetId=self.ss_id).execute(num_retries=3)
        except HttpError as e:
            handleHttpError(e)
            self._get_resource(n=n+1)
        else:
            self.propObj = self.ssObj['properties']
            #log.debug('Opened "%s" ss.', self.propObj['title'])

    #---------------------------------------------------------------
    def __init__(self, oauth, ss_id):

        self.service = auth(
            oauth,
            name='sheets',
            scopes=['https://www.googleapis.com/auth/spreadsheets'],
            version='v4')
        self.ss_id = ss_id
        self._get_resource()

#-------------------------------------------------------------------------------
class Wks():

    service = None
    ss_id = None
    title = None
    headerValues = None # Cached
    sheetObj = None # Sheet resource
    propObj = None # SheetProperties resource

    #---------------------------------------------------------------
    def _refresh(self):
        self.sheetObj = _ss_get(self.service, self.ss_id)
        self.propObj = self.sheetObj['properties']

    #---------------------------------------------------------------
    def _getLastRow(self):
        start = to_range(1,1)
        end = to_range(self.numRows(), self.numColumns())
        val_rng = _ss_values_get(
            self.service, self.ss_id, self.title, "%s:%s"%(start,end))

        lastDataRow = 1
        r = re.compile('[a-zA-Z0-9]')

        for i in range(0, len(val_rng['values'])):
            row = val_rng['values'][i]

            if len(filter(r.match, row)) > 0:
                lastDataRow = i+1
        return lastDataRow

    #---------------------------------------------------------------
    def numColumns(self):
        return self.propObj['gridProperties']['columnCount']

    #---------------------------------------------------------------
    def numRows(self):
        return self.propObj['gridProperties']['rowCount']

    #---------------------------------------------------------------
    def getRow(self, row):
        a1 = '%s:%s' % (str(row),str(row))
        return _ss_values_get(
            self.service, self.ss_id, self.title, a1)['values'][0]

    #---------------------------------------------------------------
    def getValues(self, a1):
        return _ss_values_get(
            self.service, self.ss_id, self.title, a1)['values']

    #---------------------------------------------------------------
    def updateCell(self, value, row=None, col=None, col_name=None):
        if not col_name:
            cell = to_range(row,col)
            _ss_values_update(
                self.service, self.ss_id, self.title, cell, [[value]])
        else:
            hdr = self.getRow(1)
            cell = to_range(row, hdr.index(col_name)+1)
            _ss_values_update(
                self.service, self.ss_id, self.title, cell, [[value]])
        self._refresh()

        log.debug('Updated cell %s', cell)

    #---------------------------------------------------------------
    def updateRange(self, a1, values):

        _ss_values_update(
            self.service, self.ss_id, self.title, a1, values)
        self._refresh()

        log.debug('Updated range %s', a1)

    #---------------------------------------------------------------
    def updateRanges(self, ranges, values):
        """Update values for discontinuous rows.
        given non-continuous ranges (i.e. need to
        skip over updating certain rows).
        @ranges: list of range strings. Same length as values.
        @values: list of row values for each range. Same length as ranges.
        """

        if len(ranges) != len(values):
            raise Exception('Failed to updateRanges. Ranges/Values lists diferent lengths')

        data = []
        for i in xrange(0, len(ranges)):
            data.append({
                "majorDimension": "ROWS",
                'range': ranges[i],
                'values': values[i]
            })

        try:
			self.service.spreadsheets().values().batchUpdate(
				spreadsheetId = self.ss_id,
				body = {
                    "valueInputOption": 'USER_ENTERED',
                    "data": data
                }
			).execute(num_retries=3)
        except HttpError as e:
			handleHttpError(e)

    #---------------------------------------------------------------
    def textFormat(self, text_format, ranges):
        """
        @text_format: TextFormat Object:{
          "foregroundColor": {
              object(Color)
            },
            "fontFamily": string,
            "fontSize": number,
            "bold": boolean,
            "italic": boolean,
            "strikethrough": boolean,
            "underline": boolean,
        }
        @ranges: list of [row,col] cell values

        Examples:
        text_format = {'foregroundColor': {'red': 0.5,'green': 0.5,'blue': 1.0,'alpha': 1.0}}
        text_format = {'bold':True}

        RepeatCell request:
        https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/request#RepeatCellRequest
        CellFormat Object (userEnteredFormat value):
        https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets#CellFormat
        """

        print 'properties=%s' % self.propObj

        requests = []

        for r in ranges:
            requests.append({
                'repeatCell': {
                    'fields': 'userEnteredFormat(textFormat)',
                    'range': {
                        "sheetId": self.propObj.get('sheetId',0),
                        "startRowIndex": r[0]-1, # inclusive
                        "endRowIndex": r[0], # exclusive
                        "startColumnIndex": r[1]-1, # inclusive
                        "endColumnIndex": r[1] # exclusive
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'textFormat': text_format
                        }
                    }
                }
            })

        try:
			result = self.service.spreadsheets().batchUpdate(
                spreadsheetId = self.ss_id,
                body = {"requests": requests}
			).execute(num_retries=3)
        except HttpError as e:
			handleHttpError(e)
        else:
            log.debug('result=%s', result)

    #---------------------------------------------------------------
    def appendRows(self, values):

        lastRow = self._getLastRow()
        a1_start = to_range(lastRow + 1,1)
        a1_end = to_range(lastRow + 1 + len(values), self.numColumns())
        a1 = '%s:%s' % (a1_start, a1_end)

        log.debug('Appending %s rows to row %s', len(values), lastRow+1)

        if lastRow + 1 + len(values) > self.numRows():
            _ss_values_append(self.service, self.ss_id, self.title, a1, values)
        else:
            _ss_values_update(self.service, self.ss_id, self.title, a1, values)
        self._refresh()

    #---------------------------------------------------------------
    def __init__(self, service, ss_id, sheetObj):

        self.service = service
        self.sheetObj = sheetObj
        self.ss_id = ss_id
        self.propObj = sheetObj['properties']
        self.title = sheetObj['properties']['title']

        log.debug('Opened "%s" wks.', self.title)
