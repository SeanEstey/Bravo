'''app.main.agency'''
from flask import g, request
from app import get_keys
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def get_admin_prop():

    #TODO 'n_alice_received': do aggregate of 'messages' field
    #TODO 'n_emails_sent': aggregate all 'type':'email' linked with agcy events

    return {
        'n_alice_convos': g.db['alice_chats'].find({'group':g.user.agency}).count(),
        'n_maps_indexed': len(g.db.maps.find_one({'agency':g.user.agency})['features']),
        'n_notific_events': g.db.events.find({'agency':g.user.agency}).count(),
        'n_leaderboard_accts': g.db['accts_cache'].find({'group':g.group}).count(),
        'n_users': g.db.users.find({'agency':g.user.agency}).count(),
        'n_sessions': g.db.command("collstats", "sessions")['count']
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
            {'name':g.user.agency},
            {'$set':{request.form['field']:request.form['value']}}
        )
    except Exception as e:
        log.error(str(e))

    return True
