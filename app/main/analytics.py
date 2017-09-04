# analytics.py
from flask import g
import json, logging
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
from app import get_keys
from app.lib.timer import Timer
log = logging.getLogger(__name__)

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
