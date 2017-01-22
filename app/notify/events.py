'''app.notify.events'''
import logging
from datetime import datetime,date,time
from dateutil.parser import parse
from bson.objectid import ObjectId
from flask import g
from .. import get_keys, utils
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def add(agency, name, event_date, _type):
    '''Creates a new job and adds to DB
    @conf: db.agencies->'reminders'
    Returns:
      -id (ObjectId)
    '''

    return g.db['notific_events'].insert_one({
        'name': name,
        'agency': agency,
        'event_dt': utils.naive_to_local(datetime.combine(event_date, time(8,0))),
        'type': _type,
        'status': 'pending',
        'opt_outs': 0,
        'trig_ids': []
    }).inserted_id

#-------------------------------------------------------------------------------
def get(evnt_id, local_time=True):
    event = g.db['notific_events'].find_one({'_id':evnt_id})

    if local_time == True:
        return utils.localize(event)

    return event

#-------------------------------------------------------------------------------
def get_list(agency, local_time=True, max=20):
    '''Return list of all events for agency
    '''

    sorted_events = list(g.db['notific_events'].find(
        {'agency':agency}).sort('event_dt',-1).limit(max))

    if local_time == True:
        for event in sorted_events:
            event = utils.localize(event)

    return sorted_events

#-------------------------------------------------------------------------------
def get_triggers(evnt_id, local_time=True, sort_by='type'):
    trigger_list = list(g.db['triggers'].find({'evnt_id':evnt_id}).sort(sort_by,1))

    if local_time == True:
        for trigger in trigger_list:
            trigger = utils.localize(trigger)

    return trigger_list

#-------------------------------------------------------------------------------
def get_notifics(evnt_id, local_time=True, sorted_by='account.event_dt'):
    notific_results = g.db['notifics'].aggregate([
        {'$match': {
            'evnt_id': evnt_id
            }
        },
        {'$lookup':
            {
              'from': "accounts",
              'localField': "acct_id",
              'foreignField': "_id",
              'as': "account"
            }
        },
        {'$group': {
            '_id': '$acct_id',
            'results': { '$push': '$$ROOT'}
        }}
    ])

    if local_time==True:
        # Convert to list since not possible to rewind aggregate cursors

        notific_list = list(notific_results)

        for notific in notific_list:
            notific = utils.localize(notific)

        # Returning list
        return notific_list

    # Returning cursor
    return notific_results

#-------------------------------------------------------------------------------
def reset(evnt_id):
    '''Reset the notific_event document, all triggers and associated
    notifics'''

    evnt_id = ObjectId(evnt_id)

    g.db['notific_events'].update_one(
        {'_id':evnt_id},
        {'$set':{'status':'pending'}}
    )

    n = g.db['notifics'].update(
        {'evnt_id': evnt_id}, {
            '$set': {
                'tracking.status': 'pending',
                'tracking.attempts': 0
            },
            '$unset': {
                'tracking.sid': '',
                'tracking.mid': '',
                'tracking.answered_by': '',
                'tracking.ended_dt': '',
                'tracking.speak': '',
                'tracking.code': '',
                'tracking.duration': '',
                'tracking.error': '',
                'tracking.reason': '',
                'tracking.code': '',
                'tracking.reply': '',
                'tracking.body': '',
                'tracking.sent_dt': '',
                'tracking.error_code': '',
                'tracking.digit': ''
            }
        },
        multi=True
    )

    g.db['triggers'].update(
        {'evnt_id': evnt_id},
        {'$set': {'status':'pending'}},
        multi=True
    )

    log.info('%s notifics reset', n['nModified'])

#-------------------------------------------------------------------------------
def rmv_notifics(evnt_id, acct_id):
    n_notifics = g.db['notifics'].remove({'acct_id':acct_id})['n']
    n_accounts = g.db['accounts'].remove({'_id':acct_id})['n']
    log.info('Removed %s notifics, %s account for evnt_id %s', n_notifics,
    n_accounts, evnt_id)
    return True

#-------------------------------------------------------------------------------
def dup_random_acct(evnt_id):
    import random
    random.seed()
    size = g.db.accounts.find({'evnt_id':evnt_id}).count()
    rand_num = random.randrange(size)

    acct = g.db.accounts.find({'evnt_id':ObjectId(evnt_id)}).limit(-1).skip(rand_num).next()
    notifics = g.db.notifics.find({'acct_id': acct['_id']})

    old_id = acct['_id']
    acct['_id'] = ObjectId()
    g.db.accounts.insert(acct)

    #log.info('old acct_id %s, new acct_id %s', str(old_id), str(new_acct['_id']))

    for notific in notifics:
        notific['_id'] = ObjectId()
        notific['acct_id'] = acct['_id']
        g.db.notifics.insert_one(notific)

    return True

#-------------------------------------------------------------------------------
def remove(evnt_id):
    # remove all triggers, notifics, and event
    evnt_id = ObjectId(evnt_id)

    notifics = g.db['notifics'].find({'evnt_id':evnt_id})
    for notific in notifics:
        g.db['accounts'].remove({'_id':notific['acct_id']})

    n_notifics = g.db['notifics'].remove({'evnt_id':evnt_id}).get('n')

    n_triggers = g.db['triggers'].remove({'evnt_id': evnt_id}).get('n')

    n_events = g.db['notific_events'].remove({'_id': evnt_id}).get('n')

    log.info('Removed %s event, %s notifics, and %s triggers',
        n_events, n_notifics, n_triggers)

    return True
