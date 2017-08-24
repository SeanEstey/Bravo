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
from app.main.cache import bulk_store
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
    Returns: response['result'] where response={'result':DATA, 'status':STR, 'description':ERROR_MSG}
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
        bulk_store(results if type(results) is list else [results])

    return results


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
    """Journal Entries for single account.
    eTapestry limits the number of journal entries you can retrieve for a single
    account to 100/request. The method getNextJournalEntries can be used to
    retrieve subsequent journal entries for the given account.
    @start_d, @end_d: datetime.date
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
        bulk_store(gifts, obj_type='gift')
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
        bulk_store(rv['data'])

    if with_meta:
        return rv
    else:
        return rv['data']

#-------------------------------------------------------------------------------
def mod_acct(acct_id, udf=None, persona=[], exc=False):

    try:
        call('modify_acct', data={
            'acct_id':acct_id, 'udf':udf, 'persona': persona})
    except Exception as e:
        log.error('Error modifying account %s: %s', acct_id, str(e))
        desc = str(e)
        raise Exception(desc[desc.index("u'description'")+18:desc.index("u'result'")-3])

    from flask_login import current_user
    if current_user:
        mod_by = current_user.user_id
    else:
        mod_by = 'bravo'

    r = g.db['cachedAccounts'].update_one(
        {'group':g.group,'account.id':int(acct_id)},
        {'$set':{'lastModifiedBy':mod_by}})
    #log.debug('lastModifiedBy: %s. matched=%s, n_mod=%s', mod_by,
    #r.matched_count, r.modified_count)

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
