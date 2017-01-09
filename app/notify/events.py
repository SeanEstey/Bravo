'''app.notify.events'''

import logging
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
from werkzeug import secure_filename
import codecs
from bson.objectid import ObjectId
from flask_login import current_user
import csv
import os

from .. import get_db, utils
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def add(agency, name, event_date, _type):
    '''Creates a new job and adds to DB
    @conf: db.agencies->'reminders'
    Returns:
      -id (ObjectId)
    '''
    db = get_db()
    return db['notific_events'].insert_one({
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
    db = get_db()
    event = db['notific_events'].find_one({'_id':evnt_id})

    if local_time == True:
        return utils.localize(event)

    return event

#-------------------------------------------------------------------------------
def get_list(agency, local_time=True, max=20):
    '''Return list of all events for agency
    '''

    db = get_db()
    agency = db['users'].find_one({'user': current_user.username})['agency']

    sorted_events = list(db['notific_events'].find(
        {'agency':agency}).sort('event_dt',-1).limit(max))

    if local_time == True:
        for event in sorted_events:
            event = utils.localize(event)

    return sorted_events

#-------------------------------------------------------------------------------
def get_triggers(evnt_id, local_time=True, sort_by='type'):
    db = get_db()
    trigger_list = list(db['triggers'].find({'evnt_id':evnt_id}).sort(sort_by,1))

    if local_time == True:
        for trigger in trigger_list:
            trigger = utils.localize(trigger)

    return trigger_list

#-------------------------------------------------------------------------------
def get_notifics(evnt_id, local_time=True, sorted_by='account.event_dt'):
    db = get_db()
    notific_results = db['notifics'].aggregate([
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

    db = get_db()

    db['notific_events'].update_one(
        {'_id':evnt_id},
        {'$set':{'status':'pending'}}
    )

    n = db['notifics'].update(
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

    db['triggers'].update(
        {'evnt_id': evnt_id},
        {'$set': {'status':'pending'}},
        multi=True
    )

    logger.info('%s notifics reset', n['nModified'])

#-------------------------------------------------------------------------------
def rmv_notifics(evnt_id, acct_id):
    db = get_db()
    n_notifics = db['notifics'].remove({'acct_id':acct_id})['n']
    n_accounts = db['accounts'].remove({'_id':acct_id})['n']
    logger.info('Removed %s notifics, %s account for evnt_id %s', n_notifics,
    n_accounts, evnt_id)
    return True

#-------------------------------------------------------------------------------
def dup_random_acct(evnt_id):
    db = get_db()
    import random
    random.seed()
    size = db.accounts.find({'evnt_id':evnt_id}).count()
    rand_num = random.randrange(size)

    acct = db.accounts.find({'evnt_id':ObjectId(evnt_id)}).limit(-1).skip(rand_num).next()
    notifics = db.notifics.find({'acct_id': acct['_id']})

    old_id = acct['_id']
    acct['_id'] = ObjectId()
    db.accounts.insert(acct)

    #logger.info('old acct_id %s, new acct_id %s', str(old_id), str(new_acct['_id']))

    for notific in notifics:
        notific['_id'] = ObjectId()
        notific['acct_id'] = acct['_id']
        db.notifics.insert_one(notific)

    return True

#-------------------------------------------------------------------------------
def remove(evnt_id):
    # remove all triggers, notifics, and event
    evnt_id = ObjectId(evnt_id)

    db = get_db()
    notifics = db['notifics'].find({'evnt_id':evnt_id})
    for notific in notifics:
        db['accounts'].remove({'_id':notific['acct_id']})

    n_notifics = db['notifics'].remove({'evnt_id':evnt_id}).get('n')

    n_triggers = db['triggers'].remove({'evnt_id': evnt_id}).get('n')

    n_events = db['notific_events'].remove({'_id': evnt_id}).get('n')

    logger.info('Removed %s event, %s notifics, and %s triggers',
        n_events, n_notifics, n_triggers)

    return True
