'''app.notify.triggers'''

import logging
import os
from flask import g, request
from bson.objectid import ObjectId
from datetime import datetime,date,time
from .. import smart_emit, get_keys, utils
from app.utils import bcolors
from . import voice, email, sms
log = logging.getLogger(__name__)

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
    return g.db.notifics.find({'trig_id':trig_id}).count()

#-------------------------------------------------------------------------------
def fire(evnt_id, trig_id):
    '''Sends out all dependent sms/voice/email notifics messages
    '''

    errors = []
    status = ''
    fails = 0
    event = g.db.notific_events.find_one({'_id':evnt_id})
    agnc = event['agency']
    ready = g.db.notifics.find(
        {'trig_id':trig_id, 'tracking.status':'pending'})
    count = ready.count()
    trigger = g.db.triggers.find_one({'_id':trig_id})

    log.info('%s---------- firing %s trigger for "%s" event ----------%s',
    bcolors.OKGREEN, trigger['type'], event['name'], bcolors.ENDC)

    if os.environ.get('BRAVO_SANDBOX_MODE') == 'True':
        log.info('sandbox mode detected.')
        log.info('simulating voice/sms msgs, re-routing emails')

    g.db.triggers.update_one(
        {'_id':trig_id},
        {'$set': {
            'status': 'in-progress',
            'errors': errors
    }})

    smart_emit('trigger_status',{
        'trig_id': str(trig_id), 'status': 'in-progress'})

    for n in ready:
        try:
            if n['type'] == 'voice':
                status = voice.call(n,
                    get_keys('twilio', agnc=agnc),
                    get_keys('notifiy', agnc=agnc)['voice'])
            elif n['type'] == 'sms':
                status = sms.send(n, get_keys('twilio', agnc=agnc))
            elif n['type'] == 'email':
                status = email.send(n, get_keys('mailgun', agnc=agnc))
        except Exception as e:
            status = 'error'
            errors.append(str(e))
            log.error('error sending %s. _id=%s, msg=%s', n['type'],str(n['_id']), str(e))
        else:
            if status == 'failed':
                fails += 1
        finally:
            smart_emit('notific_status', {
                'notific_id':str(n['_id']), 'status':status})

    g.db.triggers.update_one({'_id':trig_id}, {
        '$set': {'status': 'fired', 'errors': errors}})

    smart_emit('trigger_status', {
        'trig_id': str(trig_id),
        'status': 'fired',
        'sent': count-fails-len(errors),
        'fails': fails,
        'errors': len(errors)})

    log.info('%s---------- queued: %s, failed: %s, errors: %s ----------%s',
        bcolors.OKGREEN, count-fails-len(errors), fails, len(errors),bcolors.ENDC)

    return True

#-------------------------------------------------------------------------------
def kill_task():
    '''Kill the celery task spawned by firing of this trigger. Called from view
    func so has request context.
    @request: array of str trig_id's to kill
    '''

    trigger = db.triggers.find_one({'_id':ObjectId(request.form.get('trig_id'))})

    if not trigger or not trigger.get('task_id'):
        log.error('No trigger or task_id found to kill')
        return False

    from .. import tasks
    response = tasks.kill(trigger['task_id'])
