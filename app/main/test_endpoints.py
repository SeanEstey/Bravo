# app.main.test_endpoints

import logging
from flask import g, request
from flask_login import login_required
log = logging.getLogger(__name__)
from . import main

@login_required
@main.route('/test_store', methods=['GET'])
def ljksdf():
    from datetime import datetime, timedelta
    from app.main.etapestry import get_query, get_gifts
    from app.main import cache
    #accts = get_query('R1Z',category='BPU: Runs', cache=False)
    #cache.bulk_store(accts, obj_type='account')
    """
    gifts = get_gifts(
        "1353.0.317432159", # Acct #7396
        datetime.now()-timedelta(days=100),
        datetime.now(),
        cache=False)
    cache.bulk_store(gifts, obj_type='gift')
    """
    cache.query_and_store(query='R1Z', category='BPU: Runs', obj_type='account')
    return 'ok'

@login_required
@main.route('/test_update_recent_cache', methods=['GET'])
def lsjdfljkd():
    from app.main.tasks import update_recent_cache
    update_recent_cache.delay(group=g.group)
    return 'ok'

@login_required
@main.route('/test_fix_loc', methods=['GET'])
def jlkdiw():
    documents = g.db['cachedAccounts'].find(
        {'group':'vec', 'geolocation':{'$exists':True}})

    for doc in documents:
        if not doc['geolocation']:
            continue
        g.db['cachedAccounts'].update_one(
            {'_id':doc['_id']},
            {'$set':{'geolocation.acct_address':doc['account']['address']}})
        print 'updated'

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
    from app.main.tasks import update_recent_cache
    update_recent_cache.delay()
    return 'ok'
