import json
import requests

from config import *
from app celery_app

# Call PHP eTapestry script
def call(func_name, keys, data):
  return json.loads(
    requests.post(ETAP_WRAPPER_URL, data=json.dumps({
      "func": func_name,
      "keys": keys,
      "data": data
    })).text
  )

# Extract User Defined Fields from eTap Account object. Allows
# for UDF's which contain multiple fields (Block, Neighborhood)
def get_udf(field_name, etap_account):
  field_values = []

  for field in etap_account['accountDefinedValues']:
    if field['fieldName'] == field_name:
      field_values.append(field['value'])

  return ", ".join(field_values)
