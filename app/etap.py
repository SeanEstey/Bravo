'''app.etap'''
import json, logging, os, subprocess
import requests
from flask import current_app
from datetime import datetime, date
import utils
import config
log = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def call(func, keys, data, silence_exc=False ):

    sandbox = 'true' if os.environ['BRAVO_SANDBOX_MODE'] == 'True' else 'false'

    cmds = [
        'php', '/root/bravo/php/views.php',
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

    if response['status'] != 'success':
        log.error('EtapError: func="%s", \nDescription: %s',
            func, response['description'])
        raise EtapError(response['description'])
    else:
        return response['result']

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
