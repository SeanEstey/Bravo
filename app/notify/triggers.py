import logging
from bson.objectid import ObjectId
from datetime import datetime,date,time

from app import app, db
from app import utils
from app.notify import notifications

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def add(event_id, _date, _time, _type):
    '''Inserts new trigger to DB, updates event with it's id.
    @_date: naive, non-localized datetime.date
    @_time: naive, non-localized datetime.time
    @_type: 'phone' or 'email'
    Returns:
        -id (ObjectId)
    '''

    _id = db['triggers'].insert_one({
        'event_id': event_id,
        'status': 'pending',
        'type': _type,
        'fire_dt': utils.naive_to_local(datetime.combine(_date, _time))
    }).inserted_id

    db['notification_events'].update_one(
        {'_id':event_id},
        {'$push':{'triggers':{'id':_id}}})

    return _id

#-------------------------------------------------------------------------------
def fire(event_id, trig_id):
    '''Send out all notifications for this trigger for given event
    '''

    notific_event = db['notification_events'].find_one({'_id':event_id})
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
    ready_triggers = db['triggers'].find(
        {'status':'pending', 'fire_dt':{'$lt':datetime.utcnow()}})

    for trigger in ready_triggers:
        logger.info('firing %s trigger %s', trigger['type'], str(trigger['_id']))

        # Send notifications
        fire(trigger['event_id'], trigger['_id'])

    #if datetime.utcnow().minute == 0:
    pending_triggers = db['triggers'].find({'status':'pending'})

    print '%s pending triggers' % pending_triggers.count()

    return True
