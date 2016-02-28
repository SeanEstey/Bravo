import json
import requests

from config import *

def call(func_name, keys, data):
  return json.loads(
    requests.post(ETAP_WRAPPER_URL, data=json.dumps({
      "func": func_name,
      "keys": keys,
      "data": data
    })).text
  )
