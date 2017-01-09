'''app.notify.triggers'''

import logging
import os
from flask import request
from bson.objectid import ObjectId
from datetime import datetime,date,time

from app import task_emit
from .. import get_db, utils, bcolors
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

    db = get_db()

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
    db = get_db()
    trig = db['triggers'].find_one({'_id':trig_id})

    if local_time == True:
        return utils.localize(trig)

    return trig

#-------------------------------------------------------------------------------
def get_count(trig_id):
    db = get_db()
    return db['notifics'].find({'trig_id':trig_id}).count()

#-------------------------------------------------------------------------------
def fire(evnt_id, trig_id):
    '''Sends out all dependent sms/voice/email notifics messages
    '''

    db = get_db()

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

    trigger = db['triggers'].find_one({'_id':trig_id})

    errors = []
    status = ''
    fails = 0
    count = ready_notifics.count()

    logger.info('%s---------- firing %s trigger for "%s" event ----------%s',
    bcolors.OKGREEN, trigger['type'], event['name'], bcolors.ENDC)

    if os.environ.get('BRAVO_SANDBOX_MODE') == 'True':
        logger.info('sandbox mode detected.')
        logger.info('simulating voice/sms msgs, re-routing emails')

    db['triggers'].update_one(
        {'_id':trig_id},
        {'$set': {
            'status': 'in-progress',
            'errors': errors
    }})

    # Calling from celery task, do not have socketio app context.
    # Make a request to server to emit msg
    task_emit('trigger_status', data={
            'trig_id': str(trig_id),
            'status': 'in-progress'})

    for notific in ready_notifics:
        try:
            if notific['type'] == 'voice':
                status = voice.call(notific, twilio_conf, notify_conf['voice'])
            elif notific['type'] == 'sms':
                status = sms.send(notific, twilio_conf)
            elif notific['type'] == 'email':
                status = email.send(notific, mailgun_conf)
        except Exception as e:
            status = 'error'
            errors.append(str(e))
            logger.error('unexpected exception. notific _id \'%s\'. %s',
                str(notific['_id']), str(e), exc_info=True)
        else:
            if status == 'failed':
                fails += 1
        finally:
            task_emit('notific_status', data={
                'notific_id': str(notific['_id']),
                'status': status})

    db['triggers'].update_one(
        {'_id':trig_id},
        {'$set': {
            'status': 'fired',
            'errors': errors
    }})

    task_emit('trigger_status', data={
        'trig_id': str(trig_id),
        'status': 'fired',
        'sent': count-fails-len(errors),
        'fails': fails,
        'errors': len(errors)})

    logger.info('%s---------- queued: %s, failed: %s, errors: %s ----------%s',
        bcolors.OKGREEN, count-fails-len(errors), fails, len(errors), bcolors.ENDC)

    return True

#-------------------------------------------------------------------------------
def kill_task():
    '''Kill the celery task spawned by firing of this trigger. Called from view
    func so has request context.
    @request: array of str trig_id's to kill
    '''

    trigger = db.triggers.find_one({'_id':ObjectId(request.form.get('trig_id'))})

    if not trigger or not trigger.get('task_id'):
        logger.error('No trigger or task_id found to kill')
        return False

    from .. import tasks
    response = tasks.kill(trigger['task_id'])
