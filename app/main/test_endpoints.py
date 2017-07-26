# app.main.test_endpoints

import logging
from flask import g, request
from flask_login import login_required
log = logging.getLogger(__name__)
from . import main

@login_required
@main.route('/test_analytics', methods=['GET'])
def _test_analytics():
    from app.main.tasks import account_analytics
    account_analytics.delay()
    return 'ok'

@login_required
@main.route('/test_cache_all', methods=['GET'])
def _test_cache_all_gifts():
    from app.main.tasks import build_gift_cache
    build_gift_cache.delay()
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

@login_required
@main.route('/test_recent', methods=['GET'])
def _test_ss():
    from app import get_keys
    from app.main.tasks import update_cache
    update_cache.delay()
    return 'ok'
