"""datatable.py
"""

import json, logging, pytz
from flask import current_app, g
from datetime import datetime, time, date, timedelta
from app import get_keys
from app.lib.timer import Timer
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get_data(start=None, end=None):

    from bson.json_util import loads,dumps

    t1 = Timer()
    g.db = current_app.db_client['test']
    data = g.db['gsheets'].find({}).limit(100)
    data = list(data)

    return loads(dumps(data))
