'''app.main.stats'''

import logging
from datetime import datetime, date, time, timedelta
import json

from .. import etap, utils, gsheets, parser
from app import db, bcolors

logger = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def update(agency, ss_id):
    '''Stats headers:
    [Block, Date, Size, New, No, Zero, Gifts, Part, Last Part, Part Diff,
     Sales Invoice, < 1L, > 1L, Receipt, Last Receipt, Receipt Diff, Estimate,
     Estimate Diff, Driver, Route, Length, Hrs, $/Gift, Projected, Avg Receipt]
    '''

    prop = parse.to_dict(agency, ss_id)

    block = parser.get_block(prop['title'])

    if parser.is_res(block):
        route_type = 'Res'
    else:
        route_type = 'Bus'

    worksheet = prop['title'][0:3] + ' ' + route_type

    conf = db.agencies.find_one({'name':agency})
    service = gsheets.gauth(conf['google']['oauth'])

    rows = gsheets.get_values(
        service,
        conf['google']['stats_ss_id'],
        worksheet+'!A:X'
    )

    row_num = find_block_row(rows, block)

    month = prop['title'][0:3]

    # Try next month (carry-over)
    if not row_num:
        months = [
            'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
        ]

        if month == 'Dec':
            month = 'Jan'
        else:
            month = months[months.index(month)+1]

        worksheet = month + ' ' + route_type

        rows = gsheets.get_values(
            service,
            conf['google']['stats_ss_id'],
            worksheet+'!A:X'
        )

        row_num = find_block_row(rows, block)

        if not row_num:
            logger.error('Stats entry not found for block ' + block)
            return False

    logger.info(worksheet)
    logger.info(row_num)

    return True

#-------------------------------------------------------------------------------
def find_block_row(rows, block):
    for idx in range(len(rows)):
        if rows[idx].index('Block') == block:
            return idx+1

    return False

#-------------------------------------------------------------------------------
def updateStats(ss_id, archive_ss_id, route):
    ss = SpreadsheetApp.openById(ss_id)

    month = route.title.substring(0,3)
    route_type = None

    if Parser.isRes(route.title_block:
        route_type = 'Res'
    elif Parser.isBus(route.title_block:
        route_type = 'Bus'

    sheet = ss.getSheetByName(month + ' ' + route_type)

    if not sheet:
        Browser.msgBox('Cannot find Stats sheet: ' + month + ' ' + route_type, Browser.Buttons.OK)
        return False

    row_index = findStatsEntryRow(sheet, route.title_block)

    # Try next month (carry-over)
    if not row_index:
        if month == 'Dec':
            month = 'Jan'
        else:
            month = route.months[route.months.index(month)+1]

        sheet = ss.getSheetByName(month + ' ' + route_type)

        row_index = findStatsEntryRow(sheet, route.title_block)

        if not row_index:
            logger.info('Stats entry not found for block ' + route.title_block)
            return False

    stats_row = sheet.getRange(row_index+1,1,1,sheet.getLastColumn()).getValues()[0]
    headers = sheet.getRange(1,1,1,sheet.getMaxColumns()).getValues()[0]

    info = route.getInfo()
    logger.info('route info:')
    logger.info(info)

    if route_type == 'Res':
        num_dropoffs = 0
        num_zeros = 0
        num_core_gifts = 0
        num_dropoff_gifts = 0

        for i=0 i<route.orders.length i+=1:
            if route.getValue(i,'Status') == 'Dropoff':
                if route.getValue(i,'$') > 0:
                    num_dropoff_gifts += 1
                num_dropoffs += 1
            else:
                if route.getValue(i,'$') == 0:
                    num_zeros+=1
                elif route.getValue(i,'$') > 0:
                    num_core_gifts+=1

        logger.info('core_gifts: %s', String(num_core_gifts))
        logger.info('route orders: %s', String(route.orders.length))
        logger.info('num dropoffs: %s', String(num_dropoffs))

        stats_row[headers.index('Size')] = route.orders.length
        stats_row[headers.index('New')] = num_dropoffs
        stats_row[headers.index('Zero')] = num_zeros
        stats_row[headers.index('Gifts')] = num_core_gifts

        stats_row[headers.index('Part')] = (num_core_gifts) / (route.orders.length - num_dropoffs)
        str_part = String(Math.floor(stats_row[headers.index('Part')]*100)) + '% '

        archive_ss = SpreadsheetApp.openById(archive_ss_id)
        archive_sheet = archive_ss.getSheetByName('Residential')
        prev_stats_index = findStatsEntryRow(archive_sheet, route.title_block)

        logger.info('prev_route_archive_row_index: ' + prev_stats_index)

        archive_headers = archive_sheet.getRange(1,1,1,archive_sheet.getMaxColumns()).getValues()[0]

        if prev_stats_index:
            prev_stats_row = archive_sheet.getRange(prev_stats_index+1,1,1,archive_sheet.getLastColumn()).getValues()[0]
            logger.info('prev_stats_row: ' + prev_stats_row)
            stats_row[headers.index('Last Part')] = prev_stats_row[archive_headers.index('Part')]
            stats_row[headers.index('Last Receipt')] = prev_stats_row[archive_headers.index('Receipt')]
            stats_row[headers.index('Part Diff')] = stats_row[headers.index('Part')] - stats_row[headers.index('Last Part')]
    # Commercial
    else:
        stats_row[headers.index('Gifts')] = info['Participants']
        #stats_row[headers.index('Part')] = info['%']

    # Notes go in 'Projected' column on Stats Sheet

    stats_row[headers.index('Projected')] = ''

    if info['Notes'].length > 0:
      stats_row[headers.index('Projected')] += "Notes: " + info['Notes'] + "\n"

    if info['Vehicle Inspection'].length > 0:
      stats_row[headers.index('Projected')] += "Truck: " + info['Vehicle Inspection'] + ". "

    if info['Mileage'].length > 0:
      stats_row[headers.index('Projected')] += "Mileage: " + info['Mileage']

    if info['Garage ($)'].length > 0:
      stats_row[headers.index('Projected')] += 'Garage: ' + info['Garage ($)']

    stats_row[headers.index('Estimate')] = info['Total']
    stats_row[headers.index('Driver')] = route.driver
    stats_row[headers.index('Hrs')] = info['Driver Hours']
    stats_row[headers.index('Depot')] = info['Depot']
    stats_row[headers.index('Trip Info')] = info['Info']

    # Write row values
    sheet.getRange(row_index+1,1,1,stats_row.length).setValues([stats_row])

    #*************** FORMULAS ********************

    # If < 1L field has value, calculate receipt $ amount
     receipt_formula = '=if(ISNUMBER(R[0]C[-2]), (0.1*R[0]C[-2])+(0.25*R[0]C[-1]),"")'
    sheet.getRange(row_index+1, headers.index('Receipt')+1, 1, 1).setFormula(receipt_formula)

    if route_type == 'Res':
        # If Receipt & Last Receipt fields have values, subtract Last Receipt from Receipt
        receipt_diff_formula = '=if(and(ISNUMBER(R[0]C[-2]),ISNUMBER(R[0]C[-1])),R[0]C[-2] - R[0]C[-1], "-")'

        # If Receipt, calculate % estimate error
        estimate_diff_formula = '=if(isnumber(R[0]C[-4]),(R[0]C[-1] - R[0]C[-4]) / R[0]C[-4], "-")'

        sheet.getRange(row_index+1, headers.index('Receipt Diff')+1, 1, 1).setFormula(receipt_diff_formula)
        sheet.getRange(row_index+1, headers.index('Estimate Diff')+1, 1, 1).setFormula(estimate_diff_formula)

    if stats_row[headers.index('Part Diff')] < 0:
        sheet.getRange(row_index+1, headers.index('Part Diff'), 1, 3).setFontColor('#e06666')
    elif stats_row[headers.index('Part Diff')] > 0:
        sheet.getRange(row_index+1, headers.index('Part Diff')+1, 1, 3).setFontColor('#6aa84f')

    '''
    catch(e):
     msg =
      route.title_block + ' update stats failed.\\n' +
      'Msg: ' + e.message + '\\n' +
      'File: ' + e.fileName + '\\n' +
      'Line: ' + e.lineNumber
      log(msg, true)
    SpreadsheetApp.getUi().alert(msg)
    }
    finally:
    log(route.title + ' added to stats sheet', true)
    }
    '''

#-------------------------------------------------------------------------------
def updateInventory(ss_id, route):
    ss = SpreadsheetApp.openById(ss_id)
    sheet = ss.getSheetByName(route.months[route.date.getMonth()])

    rows = sheet.getDataRange().getValues()
    headers = rows[0]

    for i=0 i<headers.length i+=1:
        headers[i] = headers[i].trim()

    logger.info("Headers: %s", JSON.stringify(headers))

    if not sheet:
        logger.info('No inven sheet for ' + route.months[route.date.getMonth()])
        return

    # Find dest Inventory row
    dest_row=7

    while dest_row - 1 < rows.length:
        if not rows[dest_row - 1]:
            break
        dest_row +=1

    signed_out = route.getInventoryChanges()

    # Format for write to Inventory sheet
    row = new Array(headers.length)

    for i=0 i<row.length i+=1:
        row[i] = ''

    logger.info('Inventory changes: %s ', JSON.stringify(signed_out))

    logger.info('Writing to Row %s', String(dest_row))

    if headers.index('Date') > -1:
        row[headers.index('Date')] = route.date.toLocaleDateString()

    if headers.index('Bag Buddies') > -1:
        row[headers.index('Bag Buddies')] = signed_out['Bag Buddies In']
        row[headers.index('Bag Buddies')+1] = signed_out['Bag Buddies Out']

    if headers.index('Green Bags') > -1:
        row[headers.index('Green Bags')+1] = signed_out['Green Bags']

    if headers.index('Green Logo Bags') > -1:
        row[headers.index('Green Logo Bags')] = signed_out['Green Logo Bags']

    if headers.index('White Bags') > -1:
        row[headers.index('White Bags')] = signed_out['White Bags']

    if headers.index('Green Bins') > -1:
        row[headers.index('Green Bins')] = signed_out['Green Bins Out']
        row[headers.index('Green Bins')+1] = signed_out['Green Bins In']

    if headers.index('Blue Bins') > -1:
        row[headers.index('Blue Bins')] = signed_out['Blue Bins Out']
        row[headers.index('Blue Bins')+1] = signed_out['Blue Bins In']

    if headers.index('Bottle Bins') > -1:
        row[headers.index('Bottle Bins')] = signed_out['Bottle Bins In']
        row[headers.index('Bottle Bins')+1] = signed_out['Bottle Bins Out']

    row[headers.index('Driver')] = route.driver
    row[headers.index('Block')] = route.title_block

    logger.info(JSON.stringify(row))

    sheet.getRange(dest_row,1,1,row.length).setValues([row])

    '''
    catch(e):
     msg =
      route.title_block + ' update inventory failed.\\n' +
      'Msg: ' + e.message + '\\n' +
      'File: ' + e.fileName + '\\n' +
      'Line: ' + e.lineNumber
    log(msg, true)
    SpreadsheetApp.getUi().alert(msg)
    }
    finally:
    log(route.title + ' added to inventory sheet', true)
    }'''

#-------------------------------------------------------------------------------
def calculateEstimateError():
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
    logger.info('Updated estimate error')

#-------------------------------------------------------------------------------
def projectMonthlyRevenue():
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
            logger.info('Adding receipt ' + Number(receipt_values[i]))
        elif Number(estimate_values[i]) > 0:
            projectedRevenue += Number(estimate_values[i])
            logger.info('Adding estimate ' + Number(estimate_values[i]))
        else:
            projectedRevenue += Number(avgReceipt)
            logger.info('Adding avg ' + Number(avgReceipt))

    projectedRevCol = sheet.getRange("A1:Y1").getValues()[0].index('Projected') + 1
    sheet.getRange(2, projectedRevCol).setValue(Number(projectedRevenue.toFixed(0)))
    logger.info('Updated projected revenue: ' + Number(projectedRevenue.toFixed(0)))

#-------------------------------------------------------------------------------
def clearResidentialRun():
    sheet = SpreadsheetApp.getActiveSheet()
    rows = sheet.getDataRange()
    numRows = rows.getNumRows()
    values = rows.getValues()  # 2d array

    headers = values[0]

    sheet.getRange(3,1, numRows-2,1).clear()  # Run name
    sheet.getRange(3,headers.index('Date')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('Size')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('New')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('Part')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('< 1L')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('> 1L')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('Estimate')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('Last $')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('Driver')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('Hrs')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('MPU')+1, numRows-2, 1).clear()
    sheet.getRange(3,headers.index('Projected Revenue:')+1, numRows-2, 1).clear()
    sheet.getRange(3, headers.length, numRows-2, 1).clear()   # Header is generated automatically for mileage, so find last column
