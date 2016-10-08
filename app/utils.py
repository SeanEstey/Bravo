import requests
import re
from bson import json_util
import json
import logging
import pytz
from datetime import datetime
import flask

from app import app, db

logger = logging.getLogger(__name__)

local_tz = pytz.timezone("Canada/Mountain")

#-------------------------------------------------------------------------------
def naive_to_local(dt):
    return local_tz.localize(dt, is_dst=True)

#-------------------------------------------------------------------------------
def naive_utc_to_local(dt):
    '''dt contains UTC time but has no tz. add tz and convert'''
    return dt.replace(tzinfo=pytz.utc).astimezone(local_tz)

def tz_utc_to_local(dt):
    '''dt is tz-aware. convert time and tz'''
    return dt.astimezone(local_tz)

#-------------------------------------------------------------------------------
def all_utc_to_local_time(obj, to_strftime=None):
    '''Recursively scan through MongoDB document and convert all
    UTC datetimes to local time'''

    if isinstance(obj, dict):
        for k, v in obj.iteritems():
            obj[k] = all_utc_to_local_time(v, to_strftime=to_strftime)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            obj[idx] = all_utc_to_local_time(item, to_strftime=to_strftime)
    elif isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=pytz.utc)

        obj = obj.astimezone(local_tz)

        if to_strftime:
            obj = obj.strftime(to_strftime)

    return obj

#-------------------------------------------------------------------------------
def mongo_formatter(doc, to_local_time=False, to_strftime=None, bson_to_json=False):
    '''
    @bson_to_json:
        convert ObjectIds->{'oid': 'string'}
    @to_local_time, to_strftime:
        convert utc datetimes to local time (and to string optionally)
    '''

    if to_local_time == True:
        doc = all_utc_to_local_time(doc, to_strftime=to_strftime)

    if bson_to_json == True:
        doc = json.loads(json_util.dumps(doc))

    return doc


#-------------------------------------------------------------------------------
def send_email(to, subject, body, conf):
    '''Send email via mailgun.
    @conf: 'mailgun' dict from 'agencies' DB
    Returns:
      -mid string on success
      -False on failure'''

    try:
        response = requests.post(
          'https://api.mailgun.net/v3/' + conf['domain'] + '/messages',
          auth=('api', conf['api_key']),
          data={
            'from': conf['from'],
            'to':  to,
            'subject': subject,
            'html': body
        })
    except requests.RequestException as e:
        logger.error('mailgun: %s ', str(e))
        return False

    logger.debug(response.text)

    return json.loads(response.text)['id']



#-------------------------------------------------------------------------------
def remove_quotes(s):
  s = re.sub(r'\"', '', s)
  return s

#-------------------------------------------------------------------------------
def to_title_case(s):
  s = re.sub(r'\"', '', s)
  s = re.sub(r'_', ' ', s)
  return s.title()
