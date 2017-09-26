# analytics.py
from flask import g
import json, logging, pytz
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
from app import get_keys
from app.lib.timer import Timer
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def update_route(data):

    from pprint import pprint
    pprint(data)

    try:
        data['date'] = parse(data['date']) + timedelta(hours=8)

        r = g.db['new_routes'].update_one(
            {'group':g.group, 'date':data['date'], 'block':data['block']},
            {'$set': {
                'stats.nOrders':                data.get("orders",None),
                'stats.nSkips':                 data.get("skips",None),
                'stats.nDonations':             data.get("donors",None),
                'stats.nZeros':                 data.get("zeros",None),
                'stats.estimateTotal':          data.get("estmt",None),
                'stats.receiptTotal':           data.get("receipt",None),
                'stats.estimateAvg':            data.get("donAvg",None),
                'stats.collectionRate':         data.get("collectRate",None),
                'stats.estimateMargin':         data.get("estmtMargin",None),
                'stats.estimateTrend':          data.get("estmtTrend",None),
                'driverInput.invoiceNumber':    data.get("invoice",None),
                'driverInput.mileage':          data.get('mileage',None),
                'driverInput.raName':           data.get('ra',None),
                'driverInput.driverName':       data.get('driver',None),
                'driverInput.driverTripHrs':    data.get('tripHrs',None),
                'driverInput.driverHrs':        data.get('driverHrs',None),
                'driverInput.vehicle':          data.get('vehicle',None),
                'driverInput.raHrs':            data.get('raHrs', None),
                'driverInput.vehicleInspection': data.get('inspection',None),
                'driverInput.notes':            data.get('routeNotes', None),
                'driverInput.nCages':           data.get("cages",None)
            }}
        )
    except Exception as e:
        log.exception('Error updating route data: %s', str(e))
    else:
        if r.modified_count > 0:
            log.debug('Updated %s route data for %s', data['block'],
                data['date'].strftime('%b %d'))
        else:
            log.error('No matching route to update. Block=%s, date=%s',
                data['block'], data['date'].strftime('%b %d'))

    return True

#-------------------------------------------------------------------------------
def gifts_dataset(start=None, end=None, persona=True):
    """Query all gifts in date period, stream to client in batches via socket.io connection.
    @start, @end: datetime.date
    """

    from pprint import pprint

    t1 = Timer()
    epoch = datetime(1970,1,1, tzinfo=pytz.utc)
    criteria = g.db['groups'].find_one({'name':g.group})['etapestry']['gifts']
    aggregate = g.db['cachedGifts'].aggregate([
        {'$match': {
            'group':g.group,
            'gift.approach': criteria['approach'],
            'gift.type': 5,
            'gift.date':{
                '$gte':datetime.combine(start,time()).replace(tzinfo=pytz.utc),
                '$lte':datetime.combine(end,time()).replace(tzinfo=pytz.utc)
            }
        }},
        {'$lookup': {
            'from': 'cachedAccounts',
            'localField': 'gift.accountRef',
            'foreignField': 'account.ref',
            'as': 'account'
        }},
        {'$project': {
            'gift.amount':1, 'gift.date':1, 'account.account.personaType':1
        }}
    ])

    print 'Aggregate query completed. [%sms]' %(t1.clock(t='ms'))
    t1.restart()

    data = [{
        'personaType': d['account'][0]['account']['personaType'] if len(d['account']) > 0 else None,
        'amount': d['gift']['amount'],
        'timestamp':(d['gift']['date']-epoch).total_seconds()*1000
        } for d in aggregate
    ]

    print '%s datapoints formatted for client. [%sms]' %(len(data), t1.clock(t='ms'))

    from app.main.socketio import smart_emit
    smart_emit('gift_data', data)
    smart_emit('gift_data', [])

    return True

#-------------------------------------------------------------------------------
def net_accounts(start=None, end=None):
    """Query new/cancelled accounts in given date range.
    @date, @end: datetime.date
    """

    from app.lib.dt import ddmmyyyy_to_date
    from app.main.etapestry import get_udf
    results = {}
    t1 = Timer()

    log.debug('net_accounts analytics from %s to %s', start, end)

    # Query Growth
    growth_res = {}
    start_dt = datetime.combine(start,time())
    end_dt = datetime.combine(end,time())
    cursor = g.db['cachedAccounts'].find({
        'group':g.group,
        'account.accountDefinedValues':{
            '$elemMatch':{'fieldName':'Status'}
        },
        'account.accountCreatedDate':{'$gte':start_dt, '$lte':end_dt}})
    log.debug('Queried %s Created accounts [%sms].', cursor.count(), t1.clock(t='ms'))
    t1.restart()

    for doc in cursor:
        acct = doc['account']
        k = acct['accountCreatedDate'].strftime('%b-%Y')
        if k not in growth_res:
            growth_res[k] = 1
        else:
            growth_res[k] +=1

    #log.debug('Grouped by month [%sms].', t1.clock(t='ms'))
    t1.restart()
    log.debug('New donors: %s', growth_res)

    g.db['analytics'].update_one(
        {'group':g.group},
        {'$set':{'growth':growth_res}},
        upsert=True)

    # Query Attrition
    cursor = g.db['cachedAccounts'].find({
        'group':g.group,
        'account.accountDefinedValues':{
            '$elemMatch':{'fieldName':'Date Cancelled'},
            '$elemMatch':{'fieldName':'Status','value':'Cancelled'}
        }
    })
    #log.debug('Queried %s Cancelled accounts [%sms].', cursor.count(), t1.clock(t='ms'))
    t1.restart()

    attrition = {}

    for doc in cursor:
        acct = doc['account']
        cancel_d = ddmmyyyy_to_date(get_udf('Date Cancelled', acct))

        #if cancel_d.year < start.year or cancel_d.year > end.year:
        if cancel_d < start or cancel_d > end:
            continue

        k = cancel_d.strftime('%b-%Y')

        if k not in attrition:
            attrition[k] = 1
        else:
            attrition[k] +=1

    log.debug('Attrition: %s [%sms].', attrition, t1.clock(t='ms'))
    #log.debug('%s cancels within date period. results=%s', len(results)

    g.db['analytics'].update_one(
        {'group':g.group},
        {'$set':{'attrition':attrition}},
        upsert=True)

    results['growth'] = growth_res
    results['attrition'] = attrition

    return results
