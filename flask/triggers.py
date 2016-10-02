import logging
from datetime import datetime,date,time


from app import app, db, info_handler, error_handler, debug_handler
from tasks import celery_app
import utils

logger = logging.getLogger(__name__)
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)


#-------------------------------------------------------------------------------
def add(event_id, _date, _time, _type):
    '''Inserts new trigger to DB, updates event with it's id.
    @_date: naive, non-localized datetime.date
    @_time: naive, non-localized datetime.time
    @_type: 'phone' or 'email'
    Returns:
        -id (ObjectId)
    '''

    trigger = db['triggers'].insert_one({
        'event_id': event_id,
        'status': 'pending',
        'type': _type,
        'fire_dt': utils.localize(datetime.combine(_date, _time))
    })

    db['notification_events'].update_one(
        {'_id':event_id},
        {'$push':{'triggers':{'id':trigger['_id']}})

    return trigger['_id']
    
#-------------------------------------------------------------------------------
@celery_app.task
def fire(event_id, trig_id):
    trig_id = ObjectId(trig_id)

    reminders = db['reminders'].find({},
        {'notifications':{'$elemMatch':{'trig_id':trig_id}}})

    num = 0
    for reminder in reminders:
        if 'no_pickup' in reminder['custom']:
            continue

        notification = reminder['notification'][0]

        if notification['type'] == 'voice':
            fire_voice_call(reminder['agency'], notification)
        elif notification['type'] == 'sms':
            fire_sms(reminder['agency'], notification)
        elif notification['type'] == 'email':
            fire_email(reminder['agency'], notification)

        num+=1

    logger.info('trigger_id %s fired. %s notifications sent',
        str(trig_id), num)


#-------------------------------------------------------------------------------
def monitor_all():
    # Find all jobs with pending triggers
    expired_triggers = db['triggers'].find(
        {'status':'pending', 'fire_dt':{'$lt':datetime.utcnow()}})

    for trigger in expired_triggers:
        # Start new job
        db['triggers'].update_one(trigger, {'$set':{'status': 'fired'}})

        fire_trigger.apply_async(
            args=(str(job['_id']), str(trigger['_id']),),
            queue=app.config['DB']
        )

    if datetime.utcnow().minute == 0:
        logger.info('%d pending triggers', num)

    return True
