import logging
from bson.objectid import ObjectId
from datetime import datetime,date,time

from app import utils
from app.notify import notifications

from app import db
from app.utils import local_tz

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

    #trig = db.triggers.aggregate([
    #    {'$match': {'_id': trig_id}},
    #    {'$project': {'fire_dt':{'$add': ['$fire_dt', 25200000]}, 'fields':'$$ROOT'}}
    #    ])

    #if local_time == True:
    #    trig['fire_dt'] =  trig['fire_dt'].astimezone(local_tz)


#-------------------------------------------------------------------------------
def fire(evnt_id, trig_id):
    '''Sends out all dependent sms/voice/email notifications messages
    Important: requires Flask context if called from celery task
    '''

    notific_event = db['notification_events'].find_one({'_id':evnt_id})
    agency_conf = db['agencies'].find_one({'name':notific_event['agency']})

    notific_results = db['notifications'].find({'trig_id':trig_id})

    fails = 0

    for notific in notific_results:
        response = notifications.send(notific, agency_conf)

        if response == False:
            fails += 1

    db['triggers'].update_one({'_id':trig_id}, {'$set':{'status': 'fired'}})

    logger.info('trigger_id %s fired. %s notifications sent, %s failed',
        str(trig_id), (notific_results.count()-fails), fails)

    return True

#-------------------------------------------------------------------------------
def monitor_all():
    '''Any due triggers are fired. See celeryconfig.py for heartbeat frequency.
    IMPORTANT: Requires Flask app context. Can block server if called without
    context.'''

    ready_triggers = db['triggers'].find(
        {'status':'pending', 'fire_dt':{'$lt':datetime.utcnow()}})

    for trigger in ready_triggers:
        logger.info('firing %s trigger %s', trigger['type'], str(trigger['_id']))

        # Send notifications
        logger.info('trigger not fired. uncomment line to activate')
        #fire(trigger['evnt_id'], trigger['_id'])

    #if datetime.utcnow().minute == 0:
    pending_triggers = db['triggers'].find({'status':'pending'})

    print '%s pending triggers' % pending_triggers.count()

    return True
