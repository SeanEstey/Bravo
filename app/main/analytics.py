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
    from app.main.socketio import smart_emit
    smart_emit('gift_data', data)
    smart_emit('gift_data', [])
    return True

#-------------------------------------------------------------------------------
def route_analysis(start, end, field, op, **options):
    """Run aggregate analysis on a route field over given date range.

    :field: field name in 'stats' dict
    :op: group operator ('sum','avg')
    """
    start_dt = datetime.combine(start,time())
    end_dt = datetime.combine(end,time())
    match = {
        'group':g.group,
        'date': {'$gte':start_dt, '$lte':end_dt}
    }
    for k in options:
        if k == 'prefix':
            match['block'] = {'$regex': r'%s\w+' % options[k]}
    res = g.db['new_routes'].aggregate([
        {'$match':match},
        {'$group':{'_id':'', 'result':{'$%s' % op: '$stats.%s' % field}}},
        {'$project':{'_id':0, 'result':1}}
    ])
    return list(res)[0]

#-------------------------------------------------------------------------------
def net_accounts(start, end):
    """Query new/cancelled accounts in given date range.
    @date, @end: datetime.date
    """
    from app.lib.dt import ddmmyyyy_to_date
    from app.main.etapestry import get_udf
    results = {}
    t1 = Timer()
    growth_res = {}
    start_dt = datetime.combine(start,time())
    end_dt = datetime.combine(end,time())
    cursor = g.db['cachedAccounts'].find({
        'group':g.group,
        'account.accountDefinedValues':{
            '$elemMatch':{'fieldName':'Status'}
        },
        'account.accountCreatedDate':{'$gte':start_dt, '$lte':end_dt}})
    for doc in cursor:
        acct = doc['account']
        k = acct['accountCreatedDate'].strftime('%b-%Y')
        if k not in growth_res:
            growth_res[k] = 1
        else:
            growth_res[k] +=1
    g.db['analytics'].update_one(
        {'group':g.group},
        {'$set':{'growth':growth_res}},
        upsert=True)

    cursor = g.db['cachedAccounts'].find({
        'group':g.group,
        'account.accountDefinedValues':{
            '$elemMatch':{'fieldName':'Date Cancelled'},
            '$elemMatch':{'fieldName':'Status','value':'Cancelled'}
        }
    })
    attrition = {}
    for doc in cursor:
        acct = doc['account']

        try:
            cancel_d = ddmmyyyy_to_date(get_udf('Date Cancelled', acct))
        except Exception as e:
            log.error('Invalid Date Cancelled value=%s, Acct ID=%s',
                acct['id'], get_udf('Date Cancelled', acct))
            continue

        if cancel_d < start or cancel_d > end:
            continue
        k = cancel_d.strftime('%b-%Y')
        if k not in attrition:
            attrition[k] = 1
        else:
            attrition[k] +=1
    g.db['analytics'].update_one(
        {'group':g.group},
        {'$set':{'attrition':attrition}},
        upsert=True)
    results['growth'] = growth_res
    results['attrition'] = attrition
    return results

#-------------------------------------------------------------------------------
def summary_stats():
    from app.lib.utils import mem_check
    from app.main.etapestry import get_udf
    conversations = g.db['chatlogs'].find({'group':g.group})
    n_convos = conversations.count()
    n_msg = 0
    for convo in conversations:
        for msg in convo['messages']:
            if msg['direction'] == 'in':
                n_msg+=1
    n_geolocations = g.db['cachedAccounts'].find({'group':g.group,'geolocation':{'$exists':True}}).count()
    donors = g.db['cachedAccounts'].find({'group':g.group})
    n_donors = 0
    n_mobile = 0
    for donor in donors:
        if not donor['account'].get('accountDefinedValues'):
            continue
        status =  get_udf('Status', donor['account'])
        if status and status in ['Active','Dropoff','Cancelling','Call-in','Brings In']:
            n_donors +=1
            if get_udf('SMS', donor['account']):
                n_mobile +=1
    return {
        'dbStats': g.db.command("dbstats"),
        'sysMem': mem_check(),
        'nDonors': n_donors,
        'nMobile': n_mobile,
        'nConvos': n_convos,
        'nIncSMS': n_msg,
        'nDbMaps': len(g.db.maps.find_one({'agency':g.group})['features']),
        'nDbAccts': g.db['cachedAccounts'].find({'group':g.group}).count(),
        'nDbGeoloc': n_geolocations,
        'nDbGifts': g.db['cachedGifts'].find({'group':g.group}).count()
    }
