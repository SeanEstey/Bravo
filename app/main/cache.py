"""app.main.cache
Interface for retrieving/storing eTapestry objects to MongoDB. Bulk store
prevents excessive write operations to avoid deadlocks.
"""

import json, logging
from flask import g
from datetime import datetime
from dateutil.parser import parse
from pymongo.errors import BulkWriteError
from app import get_keys
from app.lib.timer import Timer
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def store(obj, obj_type=None):
    pass

#-------------------------------------------------------------------------------
def bulk_store(objects, obj_type=None):
    """Bulk insert results to MongoDB w/ single write.
    @results: list of either Gift or Account objects
    @obj_type: 'gift' or 'account'
    """

    if len(objects) < 1:
        return

    if obj_type not in ['gift', 'account']:
        if 'id' in objects[0]:
            obj_type = 'account'
        elif 'type' in objects[0]:
            obj_type = 'gift'
        log.warning('No obj_type set. Assuming %s from 1st list item.', obj_type)

    timer = Timer()
    n_ops = 0

    if obj_type == 'account':
        collection = 'cachedAccounts'
        obj_id = 'id'
        subdoc = 'account'
        index = 'account.id'
    elif obj_type == 'gift':
        collection = 'cachedGifts'
        obj_id = 'ref'
        subdoc = 'gift'
        index = 'gift.ref'

    bulk = g.db[collection].initialize_ordered_bulk_op()
    log.debug('bulk_store objects=%s', len(objects))

    for obj in objects:
        obj = to_datetime(obj)
        query = {'group':g.group, index:obj[obj_id]}
        document = g.db[collection].find_one(query)

        if not document or not version_match(document[subdoc], obj):
            bulk.find(query).upsert().update(
              {'$set': {'group':g.group, subdoc:obj}})
            n_ops += 1

    if n_ops == 0:
        log.debug('%s/%s %ss up to date [%s]', len(objects), len(objects), obj_type, timer.clock())
        return

    try:
        results = bulk.execute()
    except BulkWriteError as bwe:
        log.exception(bwe.details)
    else:
        log_res = {k:results[k] for k in ('nModified','nUpserted','nInserted') if results[k]>0}
        log.debug("bulk_store %ss results: %s [%s]", obj_type, log_res, timer.clock())

#-------------------------------------------------------------------------------
def query_and_store(query=None, category=None, obj_type=None, get_meta=False, timeout=75):
    """Pull recent Accounts/Gifts from query and merge w/ cached records
    """

    from app.main.etapestry import call, get_query

    timer = Timer()
    start = 0
    count = 500
    queryEnd = False

    if get_meta:
        stats = call('getQueryResultStats',
            data={'queryName':query, 'queryCategory':category}, timeout=0)
        log.debug('stats=%s', stats)
        #['journalEntryCount']

    all_data = []

    while queryEnd != True:
        results = get_query(
            query,
            category=category,
            start=start,
            count=count,
            cache=False,
            with_meta=True,
            timeout=timeout)
        start += 500

        if start > results['total']:
            queryEnd = True
        if 'total' not in results:
            queryEnd = True
            log.error('Cannot determine query size. Breaking loop')

        if len(results) > 0:
            all_data += results['data']

        bulk_store(results['data'], obj_type=obj_type)

    return all_data

#-------------------------------------------------------------------------------
def version_match(stored_obj, query_obj):

    dtModifiedFields = [
        'accountLastModifiedDate', 'personaLastModifiedDate', 'lastModifiedDate']

    for field in dtModifiedFields:
        if stored_obj.get(field) != query_obj.get(field):
            return False
    return True

#-------------------------------------------------------------------------------
def build_cache():
    """MERGE THIS FUNCTION WITH pull_and_store() """

    BATCH_SIZE = 500
    query = {'name':'vec', 'category':'Bravo', 'query':'All Gift Entries'}
    g.group = query['name']

    #g.group = group['name']
    timer = Timer()
    start = 0
    count = BATCH_SIZE
    n_total = call(
        'getQueryResultStats',
        data={'queryName':query['query'], 'queryCategory':query['category']},
        timeout=0
    )['journalEntryCount']

    log.info('Task: Caching gifts [Total: %s]...', n_total)

    while start < n_total:
        results = get_query(
            query['query'],
            category=query['category'],
            start=start,
            count=count,
            cache=True,
            timeout=75)

        if len(results) == 0:
            break

        log.debug('Retrieved %s/%s gifts', start+count, n_total)

        start += BATCH_SIZE

        if start + count > n_total:
            count = start + count - n_total

    log.info('Task: Completed [%s]', timer.clock())

#-------------------------------------------------------------------------------
def analyze_gifts():
    """Create donation analytics for all cached accounts using db.cachedGifts data.
    Store results in db.cachedAccounts
    """

    log.debug('Task: Acccount Analytics...')

    for org in g.db['groups'].find({'name':'vec'}):
        g.group = org['name']
        bulk = g.db['cachedAccounts'].initialize_ordered_bulk_op()

        for acct in g.db['cachedAccounts'].find({'group':g.group}):
            total = 0
            n_gifts = 0
            gifts = g.db['cachedGifts'].find({'gift.accountRef':acct['account']['ref']})

            for gift in gifts:
                total+= gift['gift'].get('amount',0)
                n_gifts += 1 if gift['gift']['type'] == 5 else 0

            avg = total/n_gifts if n_gifts > 0 else 0

            bulk.find({'_id':acct['_id']}).upsert().update(
                {'$set':{'stats':{'total':total, 'nGifts':n_gifts, 'avg':avg}}}
            )

        results = bulk.execute()
        log.debug('Task completed')

#-------------------------------------------------------------------------------
def to_datetime(obj):
    """Convert API Object Date strings to python datetime (Account and Gift
    supported atm).
    """

    if 'id' in obj:
        acctDtFields = [
            'personaCreatedDate',
            'personaLastModifiedDate',
            'accountCreatedDate',
            'accountLastModifiedDate'
        ]

        for field in acctDtFields:
            if obj[field] and type(obj[field]) != str and type(obj[field]) != unicode:
                continue
            obj[field] = parse(obj[field]) if obj[field] else None

        return obj
    elif obj.get('type') == 5: # Gift
        giftDtFields = [
            'createdDate',
            'lastModifiedDate'
        ]

        for field in giftDtFields:
            if obj[field] and type(obj[field]) != str and type(obj[field]) != unicode:
                continue
            obj[field] = parse(obj[field]) if obj[field] else None

        dt = parse(obj['date'])
        obj['date'] = datetime(dt.year, dt.month, dt.day)
        return obj
    elif obj.get('type') == 1: # Note
        return obj

    log.error('Unknown object type=%s.', obj.get('type'))
    return obj
