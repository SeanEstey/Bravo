'''app.main.etap'''
from flask import g
from datetime import datetime
import json, logging, os, subprocess
from dateutil.parser import parse
from datetime import datetime, date
from app import get_keys
from app.lib.timer import Timer
from app.main.maps import geocode
from logging import getLogger
log = getLogger(__name__)

class EtapError(Exception):
    pass

NAME_FORMAT = {
    'NONE': 0,
    'INDIVIDUAL': 1,
    'FAMILY': 2,
    'BUSINESS': 3
}

#-------------------------------------------------------------------------------
def call(func, data=None, silence_exc=False):

    sandbox = 'true' if os.environ['BRV_SANDBOX'] == 'True' else 'false'
    conf = get_keys('etapestry')
    cmds = [
        'php', '/root/bravo/php/call.php',
        g.group, conf['user'], conf['pw'], conf['wsdl_url'],
        func,
        sandbox,
        json.dumps(data)]

    try:
        response = subprocess.check_output(cmds)
    except Exception as e:
        log.exception('Error calling "%s"', func)
        raise EtapError(e)

    try:
        response = json.loads(response)
    except Exception as e:
        log.error('not json serializable, rv=%s', response)
        raise EtapError(response)

    # Success: {'status':'SUCCESS', 'result':'<data>'}
    # Fail: {'status':'FAILED', 'description':'<str>', 'result':'<optional>'}

    if response['status'] == 'FAILED':
        #log.error('status=%s, func="%s", description="%s", result="%s"',
        #    response['status'], func, response['description'], response.get('result'))
        raise EtapError(response)
    else:
        return response['result']

#-------------------------------------------------------------------------------
def cache_gifts(_gifts):

    import copy
    gifts = copy.deepcopy(_gifts)

    #bulk = g.db['cachedAccounts'].initialize_ordered_bulk_op()

    for gift in gifts:
        for field in ['createdDate', 'lastModifiedDate']:
            gift[field] = parse(gift[field]) if gift[field] else None

        dt = parse(gift['date'])
        gift['date'] = datetime(dt.year, dt.month, dt.day)

        result = g.db['cachedGifts'].update_one(
            {'group':g.group, 'gift.ref':gift['ref']},
            {'$set':{'gift':gift}},
            upsert=True)

    log.debug('Cached %s gifts', len(gifts))

#-------------------------------------------------------------------------------
def cache_accts(accts):
    '''Cache eTapestry Account objects along with their geolocation data'''

    if g.group == 'wsf':
        return

    timer = Timer()
    timer.start()

    log.debug('Caching Accounts...')

    if not 'id' in accts[0]: return # Verify Account objects

    date_fields = [
      'personaCreatedDate',
      'personaLastModifiedDate',
      'accountCreatedDate',
      'accountLastModifiedDate'
    ]
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
            # Address change?
            if cache_addr != acct_addr:
                log.debug('Acct ID %s address change (%s to %s). Updating geolocation.',
                    acct['id'], c_acct.get('address',''), acct.get('address',''))
                geo_lookup = True

        if geo_lookup:
            #log.debug('Geolocating Acct ID %s', acct['id'])

            try:
                geolocation = geocode(", ".join(acct_addr), api_key)[0]
            except Exception as e:
                log.exception('Geo lookup failed for %s', acct['address'])
            else:
                n_geolocations += 1

        for field in date_fields:
            acct[field] = parse(acct[field]) if acct[field] else None

        # Skip if already up to date
        if doc and not geo_lookup and \
           doc['account']['accountLastModifiedDate'] == acct['accountLastModifiedDate'] and \
           doc['account']['personaLastModifiedDate'] == acct['personaLastModifiedDate']:
            continue

        #log.debug('Updating Cached Account ID %s', acct['id'])

        bulk.find(
          {'group':g.group, 'account.id':acct['id']}).upsert().update(
          {'$set': {'group':g.group, 'account':acct, 'geolocation':geolocation}})
        n_ops += 1

    if n_ops > 0:
        results = bulk.execute()
        log.debug("Results: n_upserted=%s, n_Modified=%s, n_geolocations=%s [%s]",
            results['nUpserted'], results['nModified'], n_geolocations, timer.clock())
    else:
        log.debug('Already up to date. n_geolocations=%s [%s]',
            n_geolocations, timer.clock())

#-------------------------------------------------------------------------------
def get_gifts(ref, start_date, end_date):

    try:
        gifts = call(
          'get_gifts',
          data={
            'ref':ref,
            'startDate': start_date.strftime('%d/%m/%Y'),
            'endDate': end_date.strftime('%d/%m/%Y')
          })
    except Exception as e:
        log.exception('Failed to get gifts')
        raise
    else:
        log.debug('Retrieved %s gifts', len(gifts))
        cache_gifts(gifts)
        return gifts

#-------------------------------------------------------------------------------
def get_query(block, category=None, start=None, count=None, cache=True):

    try:
        rv = call(
          'get_query',
          data={
            'query':block,
            'category':category or get_keys('etapestry')['query_category'],
            'start':start,
            'count':count
          })
    except EtapError as e:
        raise
    else:
        # Cache if query returned Account objects
        if type(rv['data']) == list and len(rv['data']) > 0:
            if 'id' in rv['data'][0]:
                cache_accts(rv['data'])
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
