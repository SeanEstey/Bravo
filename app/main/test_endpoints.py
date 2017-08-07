# app.main.test_endpoints

import logging
from flask import g, request
from flask_login import login_required
from app import get_keys
log = logging.getLogger(__name__)
from . import main

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
@main.route('/test_color', methods=['GET'])
def _jkldsfkdfsjks():

    from app.lib.gsheets_cls import SS
    ss = SS(get_keys('google')['oauth'], '1ANLJ1h9K95YlTv0QKDF283q2AsRY29kuHluI2-v4T7Y')
    orders = ss.wks('Orders')
    print orders.propObj

    return 'ok'

@login_required
@main.route('/test_analytics', methods=['GET'])
def _test_analytics():
    from app.main.tasks import account_analytics
    account_analytics.delay()
    return 'ok'

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
        rows.append("%s   %s&nbsp;&nbsp;&nbsp;  $%s" %(leader['account']['id'], leader['account']['name'], leader['stats']['total']))
    return "<br>".join(rows)

#----------------------WORKING---------------------

@login_required
@main.route('/test_wipe_sessions', methods=['GET'])
def _test_wipe_sessions():

    from app import clear_sessions
    clear_sessions()
    return 'ok'

@login_required
@main.route('/test_cache_ytd', methods=['GET'])
def _test_cache_ytd():
    from app.main.tasks import build_gift_cache
    build_gift_cache.delay()
    return 'ok'

@login_required
@main.route('/test_recent', methods=['GET'])
def _test_recent():
    from app import get_keys
    from app.main.tasks import update_recent_cache
    update_recent_cache.delay()
    return 'ok'
