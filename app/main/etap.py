# app.main.etap

"""Interface for talking with eTapestry API.

Uses subprocess module to run Bravo/php/call.php script w/ arguments.
"""

import copy
from flask import g
from flask_login import current_user
from datetime import datetime
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
def get_acct(aid, cached=True):

    acct = None if cached == False else g.db['cachedAccounts'].find_one(
        {'group':g.group, 'account.id':int(aid)})
    if acct:
        return acct['account']

    return call('get_acct', data={'acct_id':int(aid)}, cache=True)

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
def get_query(name, category=None, start=None, count=None, cache=True, timeout=45):

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

    if not cache or type(rv['data']) != list or len(rv['data']) == 0:
        return rv['data']

    db_cache(rv['data'])
    return rv['data']

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
        auth['user'], auth['pw'], auth['wsdl_url'],
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
def pythonify(obj):
    '''@obj: eTapestry query result obj. Either: Account or Journal Entry subtype
    '''

    # Account
    if 'id' in obj:
        for field in ['personaCreatedDate', 'personaLastModifiedDate', 'accountCreatedDate', 'accountLastModifiedDate']:
            obj[field] = parse(obj[field]) if obj[field] else None
        return obj

    # Journal Entry

    if obj['type'] == 1: # Note
        return obj
    elif obj['type'] == 5: # Gift
        for field in ['createdDate', 'lastModifiedDate']:
            obj[field] = parse(obj[field]) if obj[field] else None
        dt = parse(obj['date'])
        obj['date'] = datetime(dt.year, dt.month, dt.day)
        return obj
    else:
        return obj

#-------------------------------------------------------------------------------
def db_cache(results):

    if 'type' in results[0]:
        _cache_gifts(results)
    elif 'id' in results[0]:
        _cache_accts(results)

#-------------------------------------------------------------------------------
def _cache_gifts(gifts):

    timer = Timer()
    bulk = g.db['cachedGifts'].initialize_ordered_bulk_op()
    n_ops = 0

    for gift in gifts:
        cached = g.db['cachedGifts'].find_one({'group':g.group, 'gift.ref':gift['ref']})

        if not cached:
            bulk.insert({'group':g.group, 'gift':pythonify(gift)})
            n_ops += 1
            continue

        gift = pythonify(gift)

        if cached['gift'].get('lastModifiedDate',None) != gift.get('lastModifiedDate',None):
            bulk.find({'_id':cached['_id']}).update_one({'$set':{'gift':gift}})
            n_ops += 1

    if n_ops > 0:
        bulk.execute()

    log.debug('Cached %s/%s gifts [%s]', n_ops, len(gifts), timer.clock())

#-------------------------------------------------------------------------------
def _cache_accts(accts):
    '''Cache eTapestry Account objects along with their geolocation data'''

    log.debug('Caching Accounts...')
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

        acct = pythonify(acct)

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

    log.debug("Cached %s/%s accounts, geolocated %s. [%s]",
        n_ops, len(accts), n_geolocations, timer.clock())

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
