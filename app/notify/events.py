import logging
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
from werkzeug import secure_filename
import codecs
from bson.objectid import ObjectId
from flask_login import current_user
import csv
import os

from app import utils
from app import db
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def insert(agency, name, event_date):
    '''Creates a new job and adds to DB
    @conf: db.agencies->'reminders'
    Returns:
      -id (ObjectId)
    '''

    return db['notification_events'].insert_one({
        'name': name,
        'agency': agency,
        'event_dt': utils.naive_to_local(datetime.combine(event_date, time(8,0))),
        'status': 'pending',
        'opt_outs': 0,
        'trig_ids': []
    }).inserted_id

#-------------------------------------------------------------------------------
def get(evnt_id, local_time=True):
    event = db['notification_events'].find_one({'_id':evnt_id})

    if local_time == True:
        return utils.all_utc_to_local_time(event)

    return event

#-------------------------------------------------------------------------------
def get_triggers(evnt_id, local_time=True):

    trigger_list = list(db['triggers'].find({'evnt_id': evnt_id}))

    if local_time == True:
        for trigger in trigger_list:
            trigger = utils.all_utc_to_local_time(trigger)

    return trigger_list

#-------------------------------------------------------------------------------
def get_notifications(evnt_id, local_time=True):
    notific_results = db['notifications'].aggregate([
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
            notific = utils.all_utc_to_local_time(notific)

        # Returning list
        return notific_list

    # Returning cursor
    return notific_results

#-------------------------------------------------------------------------------
def reset(evnt_id):
    '''Reset the notification_event document, all triggers and associated
    notifications'''

    evnt_id = ObjectId(evnt_id)

    db['notification_events'].update_one(
        {'_id':evnt_id},
        {'$set':{'status':'pending'}}
    )

    n = db['notifications'].update(
        {'evnt_id': evnt_id}, {
            '$set': {
                'status': 'pending',
                'attempts': 0,
                'opted_out': False
            },
            '$unset': {
                'account.udf.opted_out': '',
                'sid': '',
                'answered_by': '',
                'ended_at': '',
                'speak': '',
                'code': '',
                'duration': '',
                'error': '',
                'reason': '',
                'code': ''
            }
        },
        multi=True
    )

    db['triggers'].update(
        {'evnt_id': evnt_id},
        {'$set': {'status':'pending'}},
        multi=True
    )

    logger.info('%s notifications reset', n['nModified'])

#-------------------------------------------------------------------------------
def remove(evnt_id):
    # remove all triggers, notifications, and event
    evnt_id = ObjectId(evnt_id)

    n_notific = db['notifications'].remove({'evnt_id':evnt_id})

    n_triggers = db['triggers'].remove({'evnt_id': evnt_id})

    db['notification_events'].remove({'_id': evnt_id})

    logger.info('Removed %s notifications and %s triggers', n_notific, n_triggers)

    return True

#-------------------------------------------------------------------------------
def get_all(agency, local_time=True, max=10):
    '''Display jobs for agency associated with current_user
    If no 'n' specified, display records (sorted by date) {1 .. JOBS_PER_PAGE}
    If 'n' arg, display records {n .. n+JOBS_PER_PAGE}
    Returns: list of notification_event dict objects
    '''

    agency = db['users'].find_one({'user': current_user.username})['agency']

    events_curs = db['notification_events'].find({'agency':agency})

    # TODO: do this sort on the query itself
    #if events_curs:
    #    events_curs = events.sort('event_dt',-1)
        #.limit(app.config['JOBS_PER_PAGE'])

    # Convert from cursor->list so re-iterable
    #events = list(events)

    if local_time == True:
        for event in events_curs:
            event = utils.all_utc_to_local_time(event)

        events_curs.rewind()

    return events_curs
