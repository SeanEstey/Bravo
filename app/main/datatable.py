"""datatable.py
"""

import json, logging, pytz
from flask import current_app, g
from datetime import datetime, time, date, timedelta
from app import get_keys
from app.lib.timer import Timer
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get_data(start=None, end=None, tag=None):

    from bson.json_util import loads,dumps
    from dateutil.parser import parse

    limit = 1000
    t1 = Timer()

    if tag and tag == 'routes_new':
        g.db = current_app.db_client['bravo']

        data = g.db['new_routes'].find(
            {'group':'vec'} #, 'date':{'$gte':parse("Sep 7 2017 00:00:00Z")}}
        ).sort('date',-1).limit(limit)

    elif tag and tag == 'test_gsheets':
        g.db = current_app.db_client['test']

        data = g.db['gsheets'].find(
            {'group':'vec'}
        ).sort('date',-1).limit(limit)

    data = loads(dumps(list(data)))

    log.debug('Returning %s routes to datatable [%sms]', len(data), t1.clock(t='ms'))

    return data
