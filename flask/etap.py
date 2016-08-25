import json
import requests

from config import *

#-------------------------------------------------------------------------------
def call(func_name, keys, data):
    '''Call PHP eTapestry script
    keys: dict with etap keys {'agency','endpoint','user','pw'}
    Returns: any data or messages
    '''

    #if 


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
