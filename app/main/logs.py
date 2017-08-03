'''app.main.logs'''
import logging, re
from json import loads
from flask import g, request
from datetime import datetime, timedelta
from app.lib.utils import format_bson
log = logging.getLogger(__name__)

#---------------------------------------------------------------------------
def get_logs(groups=None, tags=None, levels=None, n_skip=0):

    query = {
        'level': {'$in':levels}
    }

    if tags:
        query['tag'] = {'$in': tags}

    if groups:
        if 'org_name' in groups:
            groups[groups.index('org_name')] = g.group
        query['group'] = {'$in':groups}

    #log.debug('groups=%s, tags=%s, levels=%s', groups, tags, levels)
    #print 'query=%s' % query

    logs = g.db.logs.find(query).limit(50).sort('timestamp', -1).skip(n_skip)
    return format_bson(list(logs))
