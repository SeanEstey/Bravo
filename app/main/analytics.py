'''app.main.analytics'''
import json, logging
from flask import g
from app import get_logger, get_keys
from app.lib import utils, gsheets
from . import parser
from .etap import call, EtapError, get_query, get_udf
from app.routing import parse
log = get_logger('analytics')

#-------------------------------------------------------------------------------
def get_ytd_total(neighborhood):

    accts = g.db.etap_accts.find({'neighborhood':neighborhood})
    total = 0
    for acct in accts:
        total += acct.get('ytd') or 0
    log.debug('%s ytd total=$%s', neighborhood, total)

#-------------------------------------------------------------------------------
def update_ytd_total(neighborhood):
    '''Find acct refs matching neighborhood from DB, pull their JE data from
    eTap, calculate total'''

    year = 2017
    accts = g.db.etap_accts.find({'neighborhood':neighborhood})

    try:
        accts_je_hist = call(
            'get_gift_histories',
            get_keys('etapestry'),
            data={
                "acct_refs": [x['ref'] for x in accts],
                "start": "01/01/" + str(year),
                "end": "31/12/" + str(year)})
    except Exception as e:
        raise

    log.debug('retrieved %s acct je histories', len(accts_je_hist))

    # Each list element contains list of {'amount':<float>, 'date':<str>}

    num_gifts = 0
    total = 0

    for je_hist in accts_je_hist:
        num_gifts += len(je_hist)
        acct_total = 0

        for je in je_hist:
            acct_total += je['amount']
            total += je['amount']

        if len(je_hist) > 0:
            g.db.etap_accts.update_one(
                {'ref':je_hist[0]['ref']},
                {'$set': {'ytd': acct_total}})

    log.debug('%s ytd: num_gifts=%s, total=$%s', neighborhood, num_gifts, total)

#-------------------------------------------------------------------------------
def store_accts(blocks=None):

    for query in blocks:
        accts = get_query(query, get_keys('etapestry'))

        for acct in accts:
            g.db.etap_accts.insert({
                'acct_id': acct['id'],
                'ref': acct['ref'],
                'neighborhood': get_udf('Neighborhood', acct)
            })

        log.debug('stored %s accts from %s', len(accts), query)

#-------------------------------------------------------------------------------
def populate_acct_data():

    # Get list of all scheduled blocks from calendar

    # Call store_accts() for each

    pass

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
