import json
import requests
import logging
from datetime import datetime, date

from app import utils

from app import app, db

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def call(func_name, keys, data, silence_exceptions=False):
    '''Call PHP eTapestry script
    @func_name:
        'get_num_active_processes'
        'add_accounts'
        'add_note'
        'update_note'
        'process_route_entries'
        'get_account'
        'get_accounts'
        'find_account_by_phone'
        'modify_account'
        'get_gift_histories'
        'get_upload_status'
        'get_block_size'
        'get_scheduled_block_size'
        'get_next_pickup'
        'check_duplicates'
        'no_pickup'
        'make_booking'
        'get_query_accounts'
    @keys: dict with etap keys {'agency','endpoint','user','pw'}
    @silence_exceptions: if True, returns False on exception, otherwise
    re-raises to caller method
    Returns:
      -Data in native python structures on success
    Exceptions:
      -Raises requests.RequestException on POST error (if not silenced)
    '''

    #logger.debug('etap.call data: %s', str(data))

    try:
        response = requests.post(
            app.config['ETAP_WRAPPER_URL'],
            data=json.dumps({
              "func": func_name,
              "etapestry": keys,
              "data": data
            })
        )
    except requests.RequestException as e:
        logger.error('etap exception calling %s: %s', func_name, str(e))

        if silence_exceptions == True:
            return False
        else:
            raise

    #logger.debug('etap.call response.text: %s', response.text)

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
def get_phone(phone_type, account):
    if 'phones' not in account or account['phones'] == None:
        return False

    for phone in account['phones']:
        if phone['type'] == phone_type:
            return phone

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
  
