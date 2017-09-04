# app.main.test_endpoints

import logging
from flask import g, request
from flask_login import login_required
from app import get_keys
log = logging.getLogger(__name__)
from . import main

#----------------------WORKING---------------------

@login_required
@main.route('/test_wipe_sessions', methods=['GET'])
def _test_wipe_sessions():

    from app import clear_sessions
    clear_sessions()
    return 'ok'

@login_required
@main.route('/test_cache_gifts', methods=['GET'])
def _test_cache_ytd():
    from app.main.tasks import build_gift_cache
    build_gift_cache.delay(query="All Gifts", group='wsf', start=230500)
    return 'ok'

@login_required
@main.route('/test_net', methods=['GET'])
def _test_cancels():
    from datetime import date
    from app.main.analytics import net_accounts
    net_accounts(start=date(2017,1,1),end=date.today())
    return 'ok'

#-------------------EXPERIMENTAL------------------

@login_required
@main.route('/test_recent', methods=['GET'])
def _test_recent():
    from app import get_keys
    from app.main.tasks import update_recent_cache
    update_recent_cache.delay()
    return 'ok'

@login_required
@main.route('/test_sched', methods=['GET'])
def _djkf39():
    import json
    from app.main.donors import get, schedule_dates
    from app.lib.dt import to_utc
    acct = get(5075)
    dates = schedule_dates(acct)
    utc = to_utc(obj=dates)
    g.db['cachedAccounts'].update_one({'account.id':5075},{'$set':{'schedule':utc}})
    stored = g.db['cachedAccounts'].find_one({'account.id':5075})['schedule']
    from bson.json_util import dumps
    return dumps(stored)

@login_required
@main.route('/test_leaders', methods=['GET'])
def _test_leaders():
    leaders = g.db['cachedAccounts'].find(
        {'group':'vec','stats.total':{'$exists':True}},
        {'_id':0, 'geolocation':0}
    ).sort('stats.total',-1).limit(100)
    log.debug('nLeaders=%s', leaders.count())
    rows = []
    for leader in leaders:
        rows.append("%s   %s&nbsp;&nbsp;&nbsp;  $%s" %(
        leader['account']['id'], leader['account']['name'], leader['stats']['total']))
    return "<br>".join(rows)


