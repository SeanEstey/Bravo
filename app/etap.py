'''app.etap'''

import json
import os
import requests
import logging
from flask import current_app
from datetime import datetime, date

import utils
import config
log = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def call(func, keys, data, silence_exc=False):
    '''Call PHP eTapestry script
    @func_name: name of view function
    @keys: etap auth
    @silence_exceptions: if True, returns False on exception, otherwise
    re-raises to caller method
    Returns:
      -response as python structures
    Exceptions:
      -Raises requests.RequestException on POST error (if not silenced)
    '''

    if os.environ['BRAVO_SANDBOX_MODE'] == 'True':
        sandbox = True
    else:
        sandbox = False

    try:
        response = requests.post(
            '%s/php/views.php' % os.environ['BRAVO_HTTP_HOST'],
            data=json.dumps({
              'func': func,
              'etapestry': keys,
              'data': data,
              'sandbox': sandbox}))
    except Exception as e:
        log.error('requests error=%s', str(e))
        return EtapError(str(e)) if silence_exc else False

    try:
        resp_text = json.loads(response.text)
    except Exception as e:
        log.error('not json serializable, rv=%s', response.text)
        raise EtapError(response.text)

    if response.status_code != 200:
        log.error('EtapError: func="%s", response_code=%s, \nDescription: %s',
            func, response.status_code, resp_text)
        raise EtapError(resp_text)

    return resp_text

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
