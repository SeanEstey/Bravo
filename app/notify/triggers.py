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

    trig_id = g.db.triggers.insert_one({
        'evnt_id': evnt_id,
        'status': 'pending',
        'type': _type,
        'fire_dt': utils.naive_to_local(datetime.combine(_date, _time))
    }).inserted_id

    g.db.notific_events.update_one(
        {'_id':evnt_id},
        {'$push':{'trig_ids': trig_id}})

    return trig_id

#-------------------------------------------------------------------------------
def get(trig_id, local_time=False):
    trig = g.db.triggers.find_one({'_id':trig_id})

    if local_time == True:
        return utils.localize(trig)

    return trig

#-------------------------------------------------------------------------------
def get_count(trig_id):
    return g.db.notifics.find({'trig_id':trig_id}).count()



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
