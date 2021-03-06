'''app.main.logs'''
import logging, re
from json import loads
from flask import g, request
from datetime import datetime, timedelta
from app.lib.utils import format_bson
log = logging.getLogger(__name__)

#---------------------------------------------------------------------------
def get_logs(groups=None, tags=None, levels=None, page=0):

    if page:
        n_skip = 50 * int(page)
    else:
        n_skip = 0

    query = {
        'standard.level': {'$in':levels}
    }

    if tags:
        query['standard.tag'] = {'$in': tags}

    if groups:
        if 'org_name' in groups:
            groups[groups.index('org_name')] = g.group
        query['standard.group'] = {'$in':groups}

    #log.debug('groups=%s, tags=%s, levels=%s', groups, tags, levels)
    #print 'query=%s' % query

    logs = g.db.logs.find(query,{'_id':0}).sort('standard.timestamp', -1).skip(n_skip).limit(50)
    return format_bson(list(logs))
