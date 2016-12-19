'''app.routing.parse'''

import logging
from app import gsheets
from app import db
import time
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def to_dict(agency, ss_id):
    conf = db.agencies.find_one({'name':agency})
    service = gsheets.gauth(conf['google']['oauth'])

    # get col A-B
    values = gsheets.get_values(service, ss_id, 'A:B')

    try:
        info_idx = values.index(['***Route Info***'])
        inven_idx = values.index(['***Inventory***'])
    except ValueError as e:
        logger.info('missing "Route Info" or "Inventory" in ss_id %s', ss_id)
        return False

    sub = values[info_idx+1:inven_idx]

    route_info = {}

    for elmt in sub:
        if len(elmt) == 1:
            route_info[elmt[0]] = ''
        else:
            route_info[elmt[0]] = elmt[1]

    time.sleep(1)
    prop = gsheets.get_prop(service, ss_id)

    route_info['title'] = prop['title']

    logger.debug(route_info)

    return route_info

#-------------------------------------------------------------------------------
def Route(id):
    '''
	this.id = id
	this.ss = SpreadsheetApp.openById(id)
	this.sheet = this.ss.getSheets()[0]

	data = this.sheet.getDataRange().getValues()

	this.headers = data.slice(0,1)[0]

	def getIdFilter(col_idx) :
	return def(element) :
	  return isNumber(element[col_idx])
	}
	}

	# An order is any row with numeric value in 'ID' column
	# Excludes header column, 'depot', 'office', etc
	this.orders = data.filter(getIdFilter(this.headers.indexOf('ID')))

	# Route title format: "Dec 27: R4E (Ryan)"
	this.title = this.ss.getName()
	this.title_block = Parser.getBlockFromTitle(this.title)

	date_str = this.title.substring(0, this.title.indexOf(":"))
	full_date_str = date_str + ", " + String((new Date()).getFullYear())

	this.date = new Date(full_date_str)

	logger.info("Route date: %s", this.date.toLocaleDateString())

	this.driver = this.title.substring(
        this.title.indexOf("(")+1,
        this.title.indexOf(")")
	)

	#  logger.info('New Route block: ' + this.title_block)

	this.months = [
		"Jan",
		"Feb",
		"Mar",
		"Apr",
		"May",
		"Jun",
		"Jul",
		"Aug",
		"Sep",
		"Oct",
		"Nov",
		"Dec"
	]
    '''
    return True

#-------------------------------------------------------------------------------
def getValue(order_idx, column_name):
    return True
	#return this.orders[order_idx][this.headers.indexOf(column_name)] || False

#-------------------------------------------------------------------------------
def orderToDict(idx):
    '''Converts row array from route into key/value dictionary. Used
    by RouteProcessor

	if idx >= this.orders.length:
	    return False

	order_info = this.getValue(idx,'Order Info')
	act_name_regex = /Name\:\s(([a-zA-Z]*?\s)*){1,5}/g
	account_name = ''

	# Parse Account Name from "Order Info" string
	if act_name_regex.test(order_info):
	    account_name = order_info.match(act_name_regex)[0] + '\n'

	gift = False

    if isNumber(this.orders[idx][this.headers.indexOf('$')]):
	    gift = Number(this.orders[idx][this.headers.indexOf('$')])

	return {
		'Address': this.getValue(idx, 'Address'),
		'Account Number': this.getValue(idx,'ID'),
		'Name & Address': account_name + this.getValue(idx,'Address'),
		'Gift Estimate': gift,
		'Driver Input': (this.getValue(idx,'Notes') || ''),
		'Driver Notes': (this.getValue(idx,'Driver Notes') || ''),
		'Block': this.getValue(idx,'Block').replace(/, /g, ','),
		'Neighborhood': (this.getValue(idx,'Neighborhood') || '').replace(/, /g, ','),
		'Status': this.getValue(idx,'Status'),
		'Office Notes': (this.getValue(idx,'Office Notes') || '')
	}
    '''
    return True

#-------------------------------------------------------------------------------
def getInfo():
    '''Gather Stats and Inven fields from bottom section of Route, build
    dictionary
    Returns: Dict object on success, False on error
    '''

    a = this.sheet.getRange(
        this.orders.length+3,
        1,
        this.sheet.getMaxRows()-this.orders.length+1,
        1
    ).getValues()

    # Make into 1D array of field names: ["Total", "Participants", ...]
    a = a.join('//').split('//')

    start = a.indexOf('***Route Info***')

    if start < 0:
        logger.info('cant find ***Route Info***')
        logger.info(a)
        return False
    else:
        start+=1

    a.splice(0, start)

    inven_idx = a.indexOf('***Inventory***')

    if inven_idx < 0:
        return False

	# Now left with Stats and Inventory field names

	stats_fields = a.splice(0, inven_idx)

    stats = {}

    b = this.sheet.getRange(
    this.orders.length+3,
    2,
    this.sheet.getMaxRows()-this.orders.length+1,
    1).getValues()

    b.splice(0, start)

    '''
    for i=0 i<stats_fields.length; i++:
        key = stats_fields[i]
        stats[key] = b[i][0]
    '''

    logger.info(stats)

    return stats

#-------------------------------------------------------------------------------
def getInventoryChanges():
	a = this.sheet.getRange(1,1,this.sheet.getMaxRows(),1).getValues()
	b = this.sheet.getRange(1,2,this.sheet.getMaxRows(),1).getValues()

	a = a.join('//').split('//')
	b = b.join('//').split('//')

  	inven_idx = a.indexOf('***Inventory***')

	if inven_idx < 0:
		return False

	a = a.slice(inven_idx + 1, a.length)
	b = b.slice(inven_idx + 1, b.length)

	# TODO: Loop through spliced array, make dictionary of all fields and values without referencing them by name below

	return {
		'Bag Buddies In': b[a.indexOf('Bag Buddies In')],
		'Bag Buddies Out': b[a.indexOf('Bag Buddies Out')],
		'Green Bags': b[a.indexOf('Green Bags')],
		'Green Logo Bags': b[a.indexOf('Green Logo Bags')],
		'White Bags': b[a.indexOf('White Bags')],
		'Green Bins In': b[a.indexOf('Green Bins In')],
		'Green Bins Out': b[a.indexOf('Green Bins Out')],
		'Blue Bins In': b[a.indexOf('Blue Bins In')],
		'Blue Bins Out': b[a.indexOf('Blue Bins Out')],
		'Bottle Bins In': b[a.indexOf('Bottle Bins In')],
		'Bottle Bins Out': b[a.indexOf('Bottle Bins Out')]
	}
