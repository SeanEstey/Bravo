'''app.etap'''

import json
import os
import requests
import logging
from flask import current_app
from datetime import datetime, date

import utils
from app import db
import config
logger = logging.getLogger(__name__)


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
        logger.error('etap exception calling %s: %s', func_name, str(e))

        if silence_exceptions == True:
            return False
        else:
            raise

    try:
        data = json.loads(response.text)
    except Exception as e:
        return False

    return data

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
def get_primary_phone(account):
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

#-------------------------------------------------------------------------------
def ddmmyyyy_to_dt(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy'''
    parts = ddmmyyyy.split('/')
    return datetime(int(parts[2]), int(parts[1]), int(parts[0]))

#-------------------------------------------------------------------------------
def ddmmyyyy_to_date(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy'''
    parts = ddmmyyyy.split('/')
    # Date constructor (year, month, day)
    return date(int(parts[2]), int(parts[1]), int(parts[0]))

#-------------------------------------------------------------------------------
def ddmmyyyy_to_local_dt(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy'''
    parts = ddmmyyyy.split('/')
    return utils.naive_to_local(
        datetime(int(parts[2]), int(parts[1]), int(parts[0])))

#-------------------------------------------------------------------------------
def dt_to_ddmmyyyy(dt):
    return dt.strftime('%d/%m/%Y')

#-------------------------------------------------------------------------------
def ddmmyyyy_to_mmddyyyy(ddmmyyyy):
    p = ddmmyyyy.split('/')
    return '%s/%s/%s' % (p[1],p[0],p[2])
