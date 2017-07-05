# app.lib.gsheets_cls

import gc, logging, re
from app import get_keys
from .timer import Timer
from .gsheets import to_range, _ss_get, _ss_values_get, _ss_values_update
from .gsheets import _ss_values_append, _execute, _ss_batch_update
from .gservice_acct import auth
log = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
class SS():

    service = None
    ss_id = None
    ssObj = None # Spreadsheet Resource:
    """
          "spreadsheetId": string,
          "properties": {
            object(SpreadsheetProperties)
          },
          "sheets": [{
            object(Sheet)
          }],
          "namedRanges": [{
            object(NamedRange)
          }],
          "spreadsheetUrl": string
	"""
    propObj = None # SpreadsheetProperties Resource:
    """
          "sheetId": number,
          "title": string,
          "index": number,
          "sheetType": enum(SheetType),
          "gridProperties": {
            object(GridProperties)
          },
          "hidden": boolean,
          "tabColor": {
            object(Color)
          },
          "rightToLeft": boolean,
	"""

    def wks(self, name):
        for sheet in self.ssObj['sheets']:
            if sheet['properties']['title'] == name:
                return Wks(self.service, self.ss_id, sheet)
                break

    def __init__(self, oauth, ss_id):
        self.service = auth(
            oauth,
            name='sheets',
            scopes=['https://www.googleapis.com/auth/spreadsheets'],
            version='v4')
        self.ss_id = ss_id
        self.ssObj = _ss_get(self.service, self.ss_id)
        self.propObj = self.ssObj['properties']
        log.debug('Opened "%s" ss.', self.propObj['title'])

#-------------------------------------------------------------------------------
class Wks():

    service = None
    ss_id = None
    title = None
    headerValues = None # Cached
    sheetObj = None # Sheet resource:

    """
          "properties": {
              object(SheetProperties)
          },
          "data": [{
              object(GridData)
          }],
          "merges": [{
              object(GridRange)
          }],
          "conditionalFormats": [{
              object(ConditionalFormatRule)
          }],
          "filterViews": [{
              object(FilterView)
          }],
          "protectedRanges": [{
              object(ProtectedRange)
          }],
          "basicFilter": {object(BasicFilter)
          },
          "charts": [{
              object(EmbeddedChart)
          }],
          "bandedRanges": [{
              object(BandedRange)
          }],
    """
    propObj = None # SheetProperties resource:
    """
          "sheetId": number,
          "title": string,
          "index": number,
          "sheetType": enum(SheetType),
          "gridProperties": {
            object(GridProperties)
          },
          "hidden": boolean,
          "tabColor": {
            object(Color)
          },
          "rightToLeft": boolean,
    """

    def _refresh(self):
        self.sheetObj = _ss_get(self.service, self.ss_id)
        self.propObj = self.sheetObj['properties']

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

    def numColumns(self):
        return self.propObj['gridProperties']['columnCount']

    def numRows(self):
        return self.propObj['gridProperties']['rowCount']

    def getRow(self, row):
        a1 = '%s:%s' % (str(row),str(row))
        return _ss_values_get(
            self.service, self.ss_id, self.title, a1)['values'][0]

    def getValues(self, a1):
        return _ss_values_get(
            self.service, self.ss_id, self.title, a1)['values']

    def updateCell(self, value, row=None, col=None, col_name=None):
        if not col_name:
            _ss_values_update(
                self.service, self.ss_id, self.title, to_range(row,col), [[value]])
        else:
            hdr = self.getRow(1)
            a1 = to_range(row, hdr.index(col_name)+1)
            _ss_values_update(
                self.service, self.ss_id, self.title, a1, [[value]])

        self._refresh()

    def updateRange(self, a1, values):
        _ss_values_update(
            self.service, self.ss_id, self.title, a1, values)
        self._refresh()

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

    def __init__(self, service, ss_id, sheetObj):
        self.service = service
        self.sheetObj = sheetObj
        self.ss_id = ss_id
        self.propObj = sheetObj['properties']
        self.title = sheetObj['properties']['title']

        log.debug('Opened "%s" wks.', self.title)
