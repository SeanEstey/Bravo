import json
import requests
from datetime import date

from config import *

def call_(func_name, keys, data):
    '''Same as call() wrapper but handles exceptions
    '''

    try:
        r = call(func_name, keys, data)
    except Exception as e:
        logger.error('eTapestry eror calling "%s": %s', func_name, str(e))
        return e

    return r

#-------------------------------------------------------------------------------
def call(func_name, keys, data):
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
    Returns: any data or messages
    '''

    return json.loads(
        requests.post(ETAP_WRAPPER_URL, data=json.dumps({
          "func": func_name,
          "etapestry": keys,
          "data": data
        })).text
    )

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
def ddmmyyyy_to_list(date_str):
    # Makes list [dd, mm, yyyy]

    parts = date_str.split('/')

    # Date constructor (year, month, day)
    return date(int(parts[2]), int(parts[1]), int(parts[0]))


#-------------------------------------------------------------------------------
def dt_to_ddmmyyyy(dt):
    return dt.strftime('%d/%m/%Y')




