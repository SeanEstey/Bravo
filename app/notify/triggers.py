'''app.notify.triggers'''
import logging, os
from flask import g, request
from bson.objectid import ObjectId
from datetime import datetime,date,time
from .. import get_logger, smart_emit, get_keys
from app.lib.dt import to_utc, to_local
from . import voice, email, sms
log = get_logger('notify.triggers')

#-------------------------------------------------------------------------------
def add(evnt_id, type_, date_, time_):
    '''Inserts new trigger to DB, updates event with it's id.
    @date_: naive, non-localized datetime.date
    @time_: naive, non-localized datetime.time
    @_type: 'voice_sms' or 'email'
    Returns:
        -id (ObjectId)
    '''

    trig_id = g.db.triggers.insert_one({
        'evnt_id': evnt_id,
        'status': 'pending',
        'type': type_,
        'fire_dt': to_utc(d=date_, t=time_)
    }).inserted_id

    g.db.events.update_one(
        {'_id':evnt_id},
        {'$push':{'trig_ids': trig_id}})

    return trig_id

#-------------------------------------------------------------------------------
def get(trig_id, local_time=False):
    trig = g.db.triggers.find_one({'_id':trig_id})

    if local_time == True:
        return to_local(trig)

    return trig

#-------------------------------------------------------------------------------
def get_count(trig_id):
    return g.db.notifics.find({'trig_id':trig_id}).count()

#-------------------------------------------------------------------------------
def kill_trigger():
    '''Kill the celery task spawned by firing of this trigger. Called from view
    func so has request context.
    @request: array of str trig_id's to kill
    '''

    # TODO: check if user has admin privileges to kill

    trigger = db.triggers.find_one({'_id':ObjectId(request.form.get('trig_id'))})

    if not trigger or not trigger.get('task_id'):
        log.error('No trigger or task_id found to kill')
        return False

    from .. import tasks
    response = tasks.kill(trigger['task_id'])
