'''app.main.etap'''
import json, logging, os, subprocess
from datetime import datetime, date
from app import get_logger, get_keys
import config
log = get_logger('etap')

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def call(func, keys, data, silence_exc=False ):

    sandbox = 'true' if os.environ['BRV_SANDBOX'] == 'True' else 'false'

    cmds = [
        'php', '/root/bravo/php/call.php',
        keys['agency'], keys['user'], keys['pw'],
        func,
        sandbox,
        json.dumps(data)]

    try:
        response = subprocess.check_output(cmds)
    except Exception as e:
        log.error('subprocess error. desc=%s', str(e))
        log.debug('',exc_info=True)
        raise

    try:
        response = json.loads(response)
    except Exception as e:
        log.error('not json serializable, rv=%s', response)
        raise EtapError(response)

    # Success: {'status':'SUCCESS', 'result':'<data>'}
    # Fail: {'status':'FAILED', 'description':'<str>', 'result':'<optional>'}

    if response['status'] == 'FAILED':
        log.error('status=%s, func="%s", description="%s", result="%s"',
            response['status'], func, response['description'], response.get('result'))
        raise EtapError(response)
    else:
        return response['result']

#-------------------------------------------------------------------------------
def block_size(category, query):
    '''Called from API. g.user available'''

    try:
        rv = call('get_block_size', get_keys('etapestry'),
                {'query':query, 'category':category})
    except EtapError as e:
        raise
    else:
        return rv

#-------------------------------------------------------------------------------
def route_size(category, query, date_):
    '''Called from API. g.user available'''
    try:
        rv = call('get_route_size', get_keys('etapestry'),
                {'query':query, 'category':category, 'date':date_})
    except EtapError as e:
        raise
    else:
        return rv

#-------------------------------------------------------------------------------
def get_query(block, keys, category=None):
    category_ = category if category else keys['query_category']

    try:
        rv = call('get_query', keys, {
            'query':block, 'category':category_})
    except EtapError as e:
        raise
    else:
        return rv['data']

#-------------------------------------------------------------------------------
def mod_acct(acct_id, keys, udf=None, persona=[]):
    try:
        call('modify_acct', keys, {
            'acct_id':acct_id, 'udf':udf, 'persona': persona})
    except EtapError as e:
        log.error('Error modifying account %s: %s', acct['id'], str(e))
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
