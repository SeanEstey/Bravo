'''app.notify.triggers'''

import logging
import os
from datetime import datetime,date,time

from .. import utils
from .. import db
from . import voice, email, sms

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def add(evnt_id, _type, _date, _time):
    '''Inserts new trigger to DB, updates event with it's id.
    @_date: naive, non-localized datetime.date
    @_time: naive, non-localized datetime.time
    @_type: 'voice_sms' or 'email'
    Returns:
        -id (ObjectId)
    '''

    trig_id = db['triggers'].insert_one({
        'evnt_id': evnt_id,
        'status': 'pending',
        'type': _type,
        'fire_dt': utils.naive_to_local(datetime.combine(_date, _time))
    }).inserted_id

    db['notific_events'].update_one(
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
    return db['notifics'].find({'trig_id':trig_id}).count()

#-------------------------------------------------------------------------------
def fire(evnt_id, trig_id):
    '''Sends out all dependent sms/voice/email notifics messages
    '''

    event = db['notific_events'].find_one({
        '_id':evnt_id})

    agency_conf = db['agencies'].find_one({
        'name':event['agency']})

    twilio_conf = agency_conf['twilio']
    notify_conf = agency_conf['notify']
    mailgun_conf = agency_conf['mailgun']

    ready_notifics = db['notifics'].find({
        'trig_id':trig_id,
        'tracking.status':'pending'})

    errors = []
    status = ''
    fails = 0

    for notific in ready_notifics:
        try:
            if notific['type'] == 'voice':
                status = voice.call(notific, twilio_conf, notify_conf['voice'])
            elif notific['type'] == 'sms':
                status = sms.send(notific, twilio_conf)
            elif notific['type'] == 'email':
                status = email.send(notific, mailgun_conf)
        except Exception as e:
            logger.error(str(e))
            errors.append('Notific %s failed. %s' % (str(notific['_id']), str(e)))

        if status == 'failed':
            fails += 1

    db['triggers'].update_one(
        {'_id':trig_id},
        {'$set': {
            'status': 'fired',
            'errors': errors
    }})

    logger.info('trigger_id %s fired. %s notifics sent, %s failed, %s errors',
        str(trig_id), (ready_notifics.count()-fails), fails, len(errors))

    return True
