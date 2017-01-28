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
def call(func_name, keys, data, silence_exceptions=False):
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
              'func': func_name,
              'etapestry': keys,
              'data': data,
              'sandbox_mode': sandbox
            })
        )
    except requests.RequestException as e:
        log.error('etap exception calling %s: %s', func_name, str(e))

        if silence_exceptions == True:
            return False
        else:
            raise EtapError(str(e))

    if response.status_code != 200:
        raise EtapError(json.loads(response.text))

    try:
        data = json.loads(response.text)
    except Exception as e:
        log.error(str(e))
        return False

    return data


#-------------------------------------------------------------------------------
def get_query(block, keys, category=None):
    _category = category if category else keys['query_category']

    try:
        rv = call('get_query_accounts', keys, {
            'query':block, 'query_category':_category})
    except EtapError as e:
        raise
    else:
        return rv['data']

#-------------------------------------------------------------------------------
def mod_acct(acct_id, keys, udf=None, persona=[]):
    try:
        call('modify_account', keys, {
            'id':acct_id, 'udf':udf, 'persona': persona})
    except EtapError as e:
        log.error('Error modifying account %s: %s', account['id'], str(e))
        raise

#-------------------------------------------------------------------------------
def get_udf(field_name, etap_account):
    '''Extract User Defined Fields from eTap Account object. Allows
    for UDF's which contain multiple fields (Block, Neighborhood)
    Returns: field value on success or '' if field empty
    '''

    field_values = []

    for field in etap_account['accountDefinedValues']:
        if field['fieldName'] == field_name:
          field_values.append(field['value'])

    return ", ".join(field_values)

#-------------------------------------------------------------------------------
def is_active(account):
    status = get_udf('Status', account)

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
def get_phone(_type, account):
    '''@_type: ['Voice', 'Mobile']
    '''

    if 'phones' not in account or account['phones'] == None:
        return False

    for phone in account['phones']:
        if phone['type'] == _type:
            return phone['number']

    return False

#-------------------------------------------------------------------------------
def has_mobile(account):
    if not account.get('phones'):
        return False

    for phone in account['phones']:
        if phone['type'] == 'Mobile':
            return True

    return False

#-------------------------------------------------------------------------------
def get_prim_phone(account):
    if 'phones' not in account or account['phones'] == None:
        return False

    landline = None

    for phone in account['phones']:
        if phone['type'] == 'Mobile':
            return phone['number']
        if phone['type'] == 'Voice':
            landline = phone['number']

    if landline:
        return landline
    else:
        return False
