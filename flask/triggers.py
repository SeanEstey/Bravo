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
    '''Send out all notifications for this trigger for given event
    '''
         
    trig_id = ObjectId(trig_id)
    event_id = ObjectId(event_id)
         
    notific_event = db['notification_events'].find_one({'_id':event_id})
    agency_conf = db['agencies'].find_one({'name':notific_event['agency']})

    notific_list = db['notifications'].find({'trig_id':trig_id})

    count = 0
         
    for notific in notific_list:
        if 'no_pickup' in notific['custom']:
            continue

        if notific['type'] == 'voice':
            notifications.send_voice_call(notific, agency_conf['twilio'])
        elif notification['type'] == 'sms':
            notifications.send_sms(notific, agency_conf['twilio'])
        elif notification['type'] == 'email':
            notifications.send_email(notific, agency_conf['mailgun'])

        count+=1

    db['triggers'].update_one(trigger, {'$set':{'status': 'fired'}})
         
    logger.info('trigger_id %s fired. %s notifications sent',
        str(trig_id), num)
    
    return True

#-------------------------------------------------------------------------------
def monitor_all():
    ready_triggers = db['triggers'].find(
        {'status':'pending', 'fire_dt':{'$lt':datetime.utcnow()}})

    for trigger in ready_triggers:
        # Send notifications
        fire.apply_async(
            args=(str(trigger['event_id']), str(trigger['_id']),),
            queue=app.config['DB']
        )
    
    #if datetime.utcnow().minute == 0:
    #    logger.info('%d pending triggers', num)

    return True
