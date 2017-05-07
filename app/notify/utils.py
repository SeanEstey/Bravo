'''app.notify.utils'''
import re
from flask import g
from app.lib.utils import formatter
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def intrntl_format(to):
    if not to:
        return None

    no_symbols = re.sub(r'\s|\-|\(|\)|[a-zA-Z]', '', to)

    try:
        if no_symbols[0:2] == '+1':
            return no_symbols

        if len(no_symbols) == 10:
            return '+1' + no_symbols

        if no_symbols[0] == '1':
            return '+' + no_symbols
    except Exception as e:
        log.error('invalid phone number %s', to)
        return None

#-------------------------------------------------------------------------------
def simple_dict(mongo_dict):
    return formatter(
        mongo_dict,
        to_local_time=True,
        to_strftime="%A, %B %d",
        bson_to_json=True)
