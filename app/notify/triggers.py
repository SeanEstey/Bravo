import logging
from bson.objectid import ObjectId
from datetime import datetime,date,time

from .. import utils
from .. import db
from . import notifications

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def insert(evnt_id, _date, _time, _type):
    '''Inserts new trigger to DB, updates event with it's id.
    @_date: naive, non-localized datetime.date
    @_time: naive, non-localized datetime.time
    @_type: 'phone' or 'email'
    Returns:
        -id (ObjectId)
    '''

    trig_id = db['triggers'].insert_one({
        'evnt_id': evnt_id,
        'status': 'pending',
        'type': _type,
        'fire_dt': utils.naive_to_local(datetime.combine(_date, _time))
    }).inserted_id

    db['notification_events'].update_one(
        {'_id':evnt_id},
        {'$push':{'trig_ids': trig_id}})

    return trig_id

#-------------------------------------------------------------------------------
def get(trig_id, local_time=False):
    trig = db['triggers'].find_one({'_id':trig_id})

    if local_time == True:
        return utils.all_utc_to_local_time(trig)

    return trig

#-------------------------------------------------------------------------------
def get_count(trig_id):
    return db['notifications'].find({'trig_id':trig_id}).count()

#-------------------------------------------------------------------------------
def fire(evnt_id, trig_id):
    '''Sends out all dependent sms/voice/email notifications messages
    Important: requires Flask context if called from celery task
    '''

    notific_event = db['notification_events'].find_one({'_id':evnt_id})
    agency_conf = db['agencies'].find_one({'name':notific_event['agency']})

    rdy_notifics = db['notifications'].find({
        'trig_id':trig_id,
        'status':'pending'
    })

    fails = 0

    for notific in rdy_notifics:
        response = notifications.send(notific, agency_conf)

        if response == False:
            fails += 1

    db['triggers'].update_one({'_id':trig_id}, {'$set':{'status': 'fired'}})

    logger.info('trigger_id %s fired. %s notifications sent, %s failed',
        str(trig_id), (rdy_notifics.count()-fails), fails)

    return True
