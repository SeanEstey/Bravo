# app.main.etapestry

"""Interface for talking with eTapestry API.

Wrapper library is in bravo/php/. Uses subprocess module to run Bravo/php/call.php script w/ arguments.
"""

from flask import g
import json, logging, os, subprocess
from dateutil.parser import parse
from datetime import datetime, date
from app import celery, get_keys
from app.lib.timer import Timer
from app.main.maps import geocode
log = logging.getLogger(__name__)

class EtapError(Exception):
    pass

NAME_FORMAT = {
    'NONE': 0,
    'INDIVIDUAL': 1,
    'FAMILY': 2,
    'BUSINESS': 3
}

#-------------------------------------------------------------------------------
def call(func, data=None, batch=False, cache=False, timeout=45):
    '''Call eTapestry API function from PHP script.
    Returns:
        response['result'] where response={'result':DATA, 'status':STR, 'description':ERROR_MSG}
    '''

    auth = get_keys('etapestry')
    cmds = [
        'php', '/root/bravo/php/call.php',
        g.group,
        auth['user'], auth['pw'],
        auth['wsdl_path'],
        func,
        'false',
        str(timeout),
        json.dumps(data)
    ]

    try:
        response = json.loads(subprocess.check_output(cmds))
    except Exception as e:
        log.exception('Error calling "%s"', func)
        raise EtapError(e)
    else:
        if response['status'] == 'FAILED':
            raise EtapError(response)

    results = response['result']

    if cache:
        db_cache(results if type(results) is list else [results])

    return results

#-------------------------------------------------------------------------------
def to_datetime(obj):
    """Convert API Object Date strings to python datetime (Account and Gift
    supported atm).
    """

    # Account
    if 'id' in obj:
        for field in ['personaCreatedDate', 'personaLastModifiedDate', 'accountCreatedDate', 'accountLastModifiedDate']:
            if obj[field] and type(obj[field]) != str and type(obj[field]) != unicode:
                continue
            obj[field] = parse(obj[field]) if obj[field] else None

        # TODO: Iterate though accountDefinedValues, convert 'datatype' == 1 to
        # datetime obj. Go through receipting code to change any references
        # to Dropoff Date, Next Pickup Date, Signup Date from str comparison to
        # datetime comparison. Go through any other code referencing
        # cachedAccount Next Pickup Date to use datetime comparison

        return obj

    # Journal Entry

    if obj['type'] == 1: # Note
        return obj
    elif obj['type'] == 5: # Gift
        for field in ['createdDate', 'lastModifiedDate']:
            if obj[field] and type(obj[field]) != str and type(obj[field]) != unicode:
                continue
            obj[field] = parse(obj[field]) if obj[field] else None
        dt = parse(obj['date'])
        obj['date'] = datetime(dt.year, dt.month, dt.day)
        return obj
    else:
        return obj

#-------------------------------------------------------------------------------
def db_cache(results):

    if len(results) < 1:
        return

    if 'type' in results[0]:
        _cache_gifts(results)
    elif 'id' in results[0]:
        _cache_accts(results)

#-------------------------------------------------------------------------------
def _cache_gifts(gifts):
    """Cache Gift objects (type=1)
    """

    timer = Timer()
    bulk = g.db['cachedGifts'].initialize_ordered_bulk_op()
    n_inserted = 0
    n_updated = 0

    for gift in gifts:
        if gift['type'] != 5:
            continue

        cached = g.db['cachedGifts'].find_one({'group':g.group, 'gift.ref':gift['ref']})

        if not cached:
            bulk.insert({'group':g.group, 'gift':to_datetime(gift)})
            n_inserted += 1
            continue

        gift = to_datetime(gift)

        if cached['gift'].get('lastModifiedDate',None) != gift.get('lastModifiedDate',None):
            bulk.find({'_id':cached['_id']}).update_one({'$set':{'gift':gift}})
            n_updated +=1

    if n_inserted > 0 or n_updated > 0:
        results = bulk.execute()
        str_res = ''
        for key in ['nModified', 'nUpserted', 'nInserted']:
            str_res += '%s=%s/%s' % (key, results[key], len(gifts)) if results[key] > 0 else ''
        log.debug('Cache gifts: %s [%s]', str_res, timer.clock())
    else:
        log.debug('Cache gifts: %s/%s up-to-date.', len(gifts), len(gifts))

#-------------------------------------------------------------------------------
def _cache_accts(accts):
    '''Cache eTapestry Account objects along with their geolocation data'''

    #log.debug('Caching Accounts. Len=%s', len(accts))
    timer = Timer()
    n_geolocations = 0
    n_ops = 0
    api_key = get_keys('google')['geocode']['api_key']
    bulk = g.db['cachedAccounts'].initialize_ordered_bulk_op()

    for acct in accts:
        doc = g.db['cachedAccounts'].find_one(
          {'group':g.group, 'account.id':acct['id']})

        geolocation = doc.get('geolocation') if doc else None
        geo_lookup = True if not geolocation else False
        acct_addr = [acct.get('address',''), acct.get('city',''), acct.get('state','')]

        if geolocation:
            c_acct = doc['account']
            cache_addr = [c_acct.get('address', ''), c_acct.get('city',''), c_acct.get('state','')]

            if cache_addr != acct_addr:
                log.debug('Updating geolocation (address change).')
                geo_lookup = True

        if geo_lookup:
            try:
                geolocation = geocode(", ".join(acct_addr), api_key)[0]
            except Exception as e:
                log.exception('Geo lookup failed for %s', acct['address'])
            else:
                n_geolocations += 1

        acct = to_datetime(acct)

        # Skip if already up to date
        if doc and not geo_lookup and \
           doc['account']['accountLastModifiedDate'] == acct['accountLastModifiedDate'] and \
           doc['account']['personaLastModifiedDate'] == acct['personaLastModifiedDate']:
            continue

        bulk.find(
          {'group':g.group, 'account.id':acct['id']}).upsert().update(
          {'$set': {'group':g.group, 'account':acct, 'geolocation':geolocation}})
        n_ops += 1

    if n_ops > 0:
        results = bulk.execute()
        str_res = 'nGeolocated=%s' % n_geolocations if n_geolocations > 0 else ''
        for key in ['nModified', 'nUpserted', 'nInserted']:
            str_res += '%s=%s/%s' % (key, results[key], len(accts)) if results[key] > 0 else ''

        log.debug("Cache Accounts: %s [%s]", str_res, timer.clock())
    else:
        log.debug('Cache Accounts: %s/%s up-to-date.', len(accts), len(accts))

###### Convenience methods #######

#-------------------------------------------------------------------------------
def get_acct(aid, ref=None, cached=True):

    timer = Timer()
    acct = None

    if cached == True and aid:
        acct = g.db['cachedAccounts'].find_one({'group':g.group, 'account.id':int(aid)})
    elif cached == True and ref:
        acct = g.db['cachedAccounts'].find_one({'group':g.group, 'account.ref':str(ref)})

    if acct:
        #print 'get cachedAccount [%s]' % timer.clock(t='ms')
        return acct['account']

    if aid:
        return call('get_account', data={'acct_id':int(aid)}, cache=True)
    elif ref:
        return call('get_account', data={'ref':ref}, cache=True)

    raise Exception('Account not found.', extra={'aid':aid or None, 'ref':ref})

#-------------------------------------------------------------------------------
def get_journal_entries(acct_id=None, ref=None, start_d=None, end_d=None, types=None, cached=False):
    """@start_d, @end_d: datetime.date
    """

    if acct_id:
        # Try getting ref from cached account
        cached = g.db['cachedAccounts'].find_one(
            {'group':g.group, 'account.id':acct_id})

        if cached:
            ref = cached['account']['ref']
        else:
            # Pull from eTapestry
            acct = get_acct(int(acct_id))
            ref = acct['ref']

    if cached:
        # Pull from cache...
        TODO = 'Write this'
        return TODO

    je_map = {'Gift': 5, 'Note': 1}
    je_types = []

    for t in types:
        if t in je_map:
            je_types.append(je_map[t])

    # Retrieve Journal Entries and cache Gifts
    try:
        je_list = call(
            'get_journal_entries',
            data={
                "ref": ref,
                "startDate": start_d.strftime("%d/%m/%Y"),
                "endDate": end_d.strftime("%d/%m/%Y"),
                "types": je_types
            },
            cache=True)
    except Exception as e:
        log.exception('Failed to get donations for Acct #%s.', acct_id or ref,
            extra={'exception':str(e)})
        raise
    else:
        return je_list

#-------------------------------------------------------------------------------
def get_gifts(ref, start_date, end_date, cache=True):

    gifts = call('get_gifts', data={
      'ref':ref,
      'startDate': start_date.strftime("%d/%m/%Y"),
      'endDate': end_date.strftime("%d/%m/%Y")
    })

    if cache:
        db_cache(gifts)
    return gifts

#-------------------------------------------------------------------------------
def get_query(name, category=None, start=None, count=None, cache=True, with_meta=False, timeout=45):

    try:
        rv = call('get_query',
          data={
            'query':name,
            'category':category or get_keys('etapestry')['query_category'],
            'start':start,
            'count':count
          },
          timeout=timeout)
    except EtapError as e:
        raise

    if cache and type(rv['data']) is list and len(rv['data']) > 0:
        db_cache(rv['data'])

    if with_meta:
        return rv
    else:
        return rv['data']

#-------------------------------------------------------------------------------
def mod_acct(acct_id, udf=None, persona=[], exc=False):

    try:
        call('modify_acct', data={
            'acct_id':acct_id, 'udf':udf, 'persona': persona})
    except EtapError as e:
        log.error('Error modifying account %s: %s', acct_id, str(e))

        if not exc:
            return str(e)
        else:
            raise

#-------------------------------------------------------------------------------
def get_udf(field_name, acct):
    '''Extract User Defined Fields from eTap Account object. Allows
    for UDF's which contain multiple fields (Block, Neighborhood)
    Returns: field value on success or '' if field empty
    '''

    field_values = []

    for field in acct['accountDefinedValues']:
        if field['fieldName'] == field_name:
          field_values.append(field['value'])

    return ", ".join(field_values)

#-------------------------------------------------------------------------------
def is_active(acct):
    status = get_udf('Status', acct)

    if status in ['Active', 'Call-in', 'One-time', 'Cancelling', 'Dropoff']:
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def get_je_udf(field_name, je):
    field_values = []

    for field in je['definedValues']:
        if field['fieldName'] == field_name:
          field_values.append(field['value'])

    return ", ".join(field_values)

#-------------------------------------------------------------------------------
def get_phone(_type, acct):
    '''@_type: ['Voice', 'Mobile']
    '''

    if 'phones' not in acct or acct['phones'] == None:
        return False

    for phone in acct['phones']:
        if phone['type'] == _type:
            return phone['number']

    return False

#-------------------------------------------------------------------------------
def has_mobile(acct):
    if not acct.get('phones'):
        return False

    for phone in acct['phones']:
        if phone['type'] == 'Mobile':
            return True

    return False

#-------------------------------------------------------------------------------
def get_prim_phone(acct):
    if 'phones' not in acct or acct['phones'] == None:
        return False

    landline = None

    for phone in acct['phones']:
        if phone['type'] == 'Mobile':
            return phone['number']
        if phone['type'] == 'Voice':
            landline = phone['number']

    if landline:
        return landline
    else:
        return False

#-------------------------------------------------------------------------------
def block_size(category, query):
    '''Called from API. g.user available'''

    try:
        rv = call('get_block_size', data={'query':query, 'category':category})
    except EtapError as e:
        raise
    else:
        return rv

#-------------------------------------------------------------------------------
def route_size(category, query, date_):
    '''Called from API. g.user available'''

    pass

    try:
        rv = call('get_route_size', data={'query':query, 'category':category, 'date':date_})
    except EtapError as e:
        raise
    else:
        return rv
