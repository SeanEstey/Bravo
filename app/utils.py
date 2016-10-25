'''app.utils'''

import requests
import types
import re
from bson import json_util
import json
import logging
import pytz
from datetime import datetime

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
def formatter(doc, to_local_time=False, to_strftime=None, bson_to_json=False):
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
def remove_quotes(s):
  s = re.sub(r'\"', '', s)
  return s

#-------------------------------------------------------------------------------
def to_title_case(s):
  s = re.sub(r'\"', '', s)
  s = re.sub(r'_', ' ', s)
  return s.title()

#-------------------------------------------------------------------------------
def to_intl_format(to):
    if not to:
        return None

    no_symbols = re.sub(r'\s|\-|\(|\)|[a-zA-Z]', '', to)

    if no_symbols[0:2] == '+1':
        return no_symbols

    if len(no_symbols) == 10:
        return '+1' + no_symbols

    if no_symbols[0] == '1':
        return '+' + no_symbols

#-------------------------------------------------------------------------------
def print_vars(obj, depth=0, l="    "):
    '''Print vars for any object.
    @depth: level of recursion
    @l: separator string
    '''

    #fall back to repr
    if depth<0: return repr(obj)
    #expand/recurse dict

    if isinstance(obj, dict):
        name = ""
        objdict = obj
    else:
        #if basic type, or list thereof, just print
        canprint=lambda o:isinstance(o, (int, float, str, unicode, bool, types.NoneType, types.LambdaType))

        try:
            if canprint(obj) or sum(not canprint(o) for o in obj) == 0:
                return repr(obj)
        except TypeError, e:
            pass

        #try to iterate as if obj were a list
        try:
            return "[\n" + "\n".join(l + print_vars(k, depth=depth-1, l=l+"  ") + "," for k in obj) + "\n" + l + "]"
        except TypeError, e:
            #else, expand/recurse object attribs

            name = (hasattr(obj, '__class__') and obj.__class__.__name__ or type(obj).__name__)
            objdict = {}

            for a in dir(obj):
                if a[:2] != "__" and (not hasattr(obj, a) or not hasattr(getattr(obj, a), '__call__')):
                    try: objdict[a] = getattr(obj, a)
                    except Exception, e:
                        objdict[a] = str(e)

    return name + "{\n" + "\n"\
        .join(
            l + repr(k) + ": " + \
            print_vars(v, depth=depth-1, l=l+"  ") + \
            "," for k, v in objdict.iteritems()
        ) + "\n" + l + "}"

