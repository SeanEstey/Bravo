'''app.main.analytics'''
import json
from flask import g
from datetime import datetime, timedelta
from app import get_keys
from app.lib.loggy import Loggy
log = Loggy('analytics')

#-------------------------------------------------------------------------------
def calculateEstimateError():

    '''
    sheet = SpreadsheetApp.getActiveSheet()
    estimate_col = sheet.getRange("A1:Y1").getValues()[0].index('Estimate') + 1
    receipt_col = sheet.getRange("A1:Y1").getValues()[0].index('Receipt') + 1
    rows = sheet.getDataRange()
    estimate_values = sheet.getRange(3, estimate_col, rows.getNumRows(), 1).getValues()
    receipt_values = sheet.getRange(3, receipt_col, rows.getNumRows(), 1).getValues()
    diff = 0


    for i=0 i<receipt_values.length i+=1:
        if Number(receipt_values[i]) > 0 && Number(estimate_values[i]) > 0:
            diff += Number(estimate_values[i]) - Number(receipt_values[i])

    estimateError = diff / Number(sheet.getRange(2, receipt_col).getValue())
    estimateDiffCol = sheet.getRange("A1:Y1").getValues()[0].index('Estimate Diff') + 1
    sheet.getRange(2, estimateDiffCol).setValue(estimateError)
    '''
    log.info('Updated estimate error')

#-------------------------------------------------------------------------------
def projectMonthlyRevenue():

    '''
    sheet = SpreadsheetApp.getActiveSheet()
    rows = sheet.getDataRange()
    estimate_col = sheet.getRange("A1:Y1").getValues()[0].index('Estimate') + 1
    receipt_col = sheet.getRange("A1:Y1").getValues()[0].index('Receipt') + 1
    last_receipt_col = sheet.getRange("A1:Y1").getValues()[0].index('Last $') + 1
    titleColumn = sheet.getRange("A3:A").getValues()
    estimate_values = sheet.getRange(3, estimate_col, rows.getNumRows()-2, 1).getValues()
    receipt_values = sheet.getRange(3, receipt_col, rows.getNumRows()-2, 1).getValues()


    if last_receipt_col == 0:
        last_receipt_values = null
    else:
        last_receipt_values = sheet.getRange(3, last_receipt_col, rows.getNumRows()-2, 1).getValues()
        avg_receipt_col = sheet.getRange("A1:Y1").getValues()[0].index('Avg Receipt') + 1
        avgReceipt = Number(sheet.getRange(2, avg_receipt_col).getValue())
        projectedRevenue = 0

    for i=0 i<receipt_values.length i+=1:
        if Number(receipt_values[i]) > 0:
            projectedRevenue += Number(receipt_values[i])
            log.info('Adding receipt ' + Number(receipt_values[i]))
        elif Number(estimate_values[i]) > 0:
            projectedRevenue += Number(estimate_values[i])
            log.info('Adding estimate ' + Number(estimate_values[i]))
        else:
            projectedRevenue += Number(avgReceipt)
            log.info('Adding avg ' + Number(avgReceipt))

    projectedRevCol = sheet.getRange("A1:Y1").getValues()[0].index('Projected') + 1
    sheet.getRange(2, projectedRevCol).setValue(Number(projectedRevenue.toFixed(0)))
    log.info('Updated projected revenue: ' + Number(projectedRevenue.toFixed(0)))
    '''
