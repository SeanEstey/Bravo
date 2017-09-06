'''app.main.agency'''
from flask import g, request, current_app
from app import get_keys
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def get_admin_prop():

    from app.lib.utils import mem_check
    from app.main.etapestry import get_udf

    conversations = g.db['chatlogs'].find({'group':g.group})
    n_convos = conversations.count()
    n_msg = 0

    for convo in conversations:
        for msg in convo['messages']:
            if msg['direction'] == 'in':
                n_msg+=1

    n_geolocations = g.db['cachedAccounts'].find({'group':g.group,'geolocation':{'$exists':True}}).count()

    donors = g.db['cachedAccounts'].find({'group':g.group})
    n_donors = 0
    n_mobile = 0

    for donor in donors:
        if not donor['account'].get('accountDefinedValues'):
            continue
        status =  get_udf('Status', donor['account'])
        if status and status in ['Active','Dropoff','Cancelling','Call-in','Brings In']:
            n_donors +=1

            if get_udf('SMS', donor['account']):
                n_mobile +=1


    return {
        'db_stats': g.db.command("dbstats"),
        'sys_mem': mem_check(),
        'n_donors': n_donors,
        'n_mobile': n_mobile,
        'n_alice_convos': n_convos,
        'n_alice_incoming': n_msg,
        'n_maps_indexed': len(g.db.maps.find_one({'agency':g.group})['features']),
        'n_notific_events': g.db.events.find({'agency':g.group}).count(),
        'n_leaderboard_accts': g.db['accts_cache'].find({'group':g.group}).count(),
        'n_users': g.db.users.find({'group':g.group}).count(),
        'n_sessions': g.db.command("collstats", "sessions")['count'],
        'n_cached_accounts': g.db['cachedAccounts'].find({'group':g.group}).count(),
        'n_geolocations': n_geolocations,
        'n_cached_gifts': g.db['cachedGifts'].find({'group':g.group}).count()
    }

#-------------------------------------------------------------------------------
def get_conf():
    return get_keys()

#-------------------------------------------------------------------------------
def update_conf(data=None):
    log.info('updating %s with value %s', request.form['field'], request.form['value'])

    '''old_value = g.db['groups'].find_one({'name':user['agency']})[request.form['field']]

    if type(old_value) != type(request.form['value']):
        log.error('type mismatch')
        return False
    '''

    try:
        r = g.db['groups'].update_one(
            {'name':g.group},
            {'$set':{request.form['field']:request.form['value']}}
        )
    except Exception as e:
        log.error(str(e))

    return True
