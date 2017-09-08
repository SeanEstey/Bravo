# analytics.py
from flask import g
import json, logging, pytz
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
from app import get_keys
from app.lib.timer import Timer
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def gifts_dataset(start=None, end=None, persona=True):
    """Query all gifts in date period, stream to client in batches via socket.io connection.
    @start, @end: datetime.date
    """

    from pprint import pprint
    from app.main.socketio import smart_emit

    t1 = Timer()
    epoch = datetime(1970,1,1, tzinfo=pytz.utc)
    criteria = g.db['groups'].find_one({'name':g.group})['etapestry']['gifts']
    aggregate = g.db['cachedGifts'].aggregate([
        {'$match': {
            'group':g.group,
            'gift.fund': criteria['fund'],
            'gift.approach': criteria['approach'],
            'gift.campaign': criteria['campaign'],
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
    smart_emit('gift_data', data)
    smart_emit('gift_data', [])
    return True

    """
    data = None
    pos = 0
    i=1
    n_batches = 5
    batch_size = g.db['cachedGifts'].find(query).count()/n_batches +1

    # Stream data back via socket.io connection
    while data is None or len(data) > 0:

        data=[]
        giftsCurs = g.db['cachedGifts'].find(query)[pos:pos+batch_size]
        acct_refs = [n['gift']['accountRef'] for n in giftsCurs]
        acctsCurs = list(g.db['cachedAccounts'].find({'account.ref':{'$in':acct_refs}}))
        giftsCurs.rewind()
        n_persona = 0

        for doc in giftsCurs:
            gift = doc['gift']
            datapoint = {
                'amount': gift['amount'],
                'timestamp':(gift['date']-epoch).total_seconds()*1000
            }
            ref = gift['accountRef']

            for n in range(0,len(acctsCurs)):
                acct = acctsCurs[n]['account']

                if acct['ref'] == ref:
                    datapoint['personaType'] = acct['personaType']
                    n_persona +=1
                    break

            data.append(datapoint)

        # Send over socket
        smart_emit('gift_data', data)

        if len(data) > 0:
            print '[%s/%s] socketio: %s datapoints sent [%sms]' %(i, n_batches, len(data), t1.clock(t='ms'))
            t1.restart()

        pos+=batch_size
        i+=1

    return True
    """

#-------------------------------------------------------------------------------
def net_accounts(start=None, end=None):
    """Query new/cancelled accounts in given date range.
    @date, @end: datetime.date
    """

    from app.lib.dt import ddmmyyyy_to_date
    from app.main.etapestry import get_udf
    results = {}
    t1 = Timer()

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

    log.debug('Grouped by month [%sms].', t1.clock(t='ms'))
    t1.restart()
    log.debug(growth_res)

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
    log.debug('Queried %s Cancelled accounts [%sms].', cursor.count(), t1.clock(t='ms'))
    t1.restart()

    for doc in cursor:
        acct = doc['account']
        cancel_d = ddmmyyyy_to_date(get_udf('Date Cancelled', acct))

        if cancel_d.year < start.year or cancel_d.year > end.year:
            continue

        k = cancel_d.strftime('%b-%Y')

        if k not in results:
            results[k] = 1
        else:
            results[k] +=1

    log.debug('Grouped by month [%sms].', t1.clock(t='ms'))
    log.debug(results)

    g.db['analytics'].update_one(
        {'group':g.group},
        {'$set':{'attrition':results}},
        upsert=True)
