'''app.notify.tasks'''
import json, logging, os, pytz
from os import environ as env
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from bson import ObjectId as oid
from flask import g, render_template
from app import get_keys, celery, smart_emit, task_logger
from app.lib.utils import to_title_case
from app.lib.dt import to_local
from app.lib import mailgun
from app.main import cal
from app.main.etap import call, EtapError
from . import email, sms, voice, pickups, triggers
log = task_logger('notify.tasks')

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def monitor_triggers(self, **kwargs):

    # TESTING
    all_triggs = g.db.triggers.find({'status':'pending'})
    for t in all_triggs:
        evnt = g.db.events.find_one({'_id': t['evnt_id']})
        if evnt['name'] == 'R1Z':
            try:
                fire_trigger(t['_id'])
            except Exception as e:
                log.error('fire_trigger error. desc=%s', str(e))
                log.debug('',exc_info=True)
    # END TESTING

    ready = g.db.triggers.find({
        'status':'pending',
        'fire_dt':{
            '$lt':datetime.utcnow()}})

    for trigger in ready:
        log.debug('trigger %s scheduled. firing.', str(trigger['_id']))

        try:
            fire_trigger(trigger['_id'])
        except Exception as e:
            log.error('fire_trigger error. desc=%s', str(e))
            log.debug('',exc_info=True)

    pending = g.db.triggers.find({
        'status':'pending',
        'fire_dt': {
            '$gt':datetime.utcnow()}}).sort('fire_dt', 1)

    output = []

    if pending.count() > 0:
        tgr = pending.next()
        delta = tgr['fire_dt'] - datetime.utcnow().replace(tzinfo=pytz.utc)
        to_str = str(delta)[:-7]
        return 'next trigger pending in %s' % to_str
    else:
        return '0 pending'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def fire_trigger(self, _id=None, **rest):
    '''Sends out all dependent sms/voice/email notifics messages
    '''

    err = []
    status = ''
    fails = 0
    trig = g.db.triggers.find_one({'_id':oid(_id)})
    event = g.db.events.find_one({'_id':trig['evnt_id']})
    agcy = event['agency']
    g.db.triggers.update_one(
        {'_id':oid(_id)},
        {'$set': {'task_id':self.request.id, 'status':'in-progress', 'errors':err}})
    ready = g.db.notifics.find(
        {'trig_id':oid(_id), 'tracking.status':'pending'})
    count = ready.count()

    log.warning('sending %s %s notifications for %s...',
        count, to_title_case(trig['type']), event['name'])
    smart_emit('trigger_status',{
        'trig_id': str(_id), 'status': 'in-progress'})
    if env['BRV_SANDBOX'] == 'True':
        log.warning('sandbox: simulating voice/sms, rerouting emails')

    for n in ready:
        try:
            if n['type'] == 'voice':
                status = voice.call(n, get_keys('twilio',agcy=agcy))
            elif n['type'] == 'sms':
                status = sms.send(n, get_keys('twilio',agcy=agcy))
            elif n['type'] == 'email':
                status = email.send(n, get_keys('mailgun',agcy=agcy))
        except Exception as e:
            status = 'error'
            err.append(str(e))
            log.error('error sending %s to %s (%s)', n['type'], n['to'], str(e))
            log.debug('', exc_info=True)
        else:
            if status == 'failed':
                fails += 1
        finally:
            smart_emit('notific_status', {
                'notific_id':str(n['_id']), 'status':status})

    g.db.triggers.update_one({'_id':oid(_id)}, {
        '$set': {'status': 'fired', 'errors': err}})

    smart_emit('trigger_status', {
        'trig_id': str(_id),
        'status': 'fired',
        'sent': count - fails - len(err),
        'fails': fails,
        'errors': len(err)})

    log.warning('notifications sent. %s queued, %s failed, %s errors.',
        count - fails - len(err), fails, len(err))
    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def schedule_reminders(self, agcy=None, for_date=None, **rest):

    if for_date:
        for_date = parse(for_date).date()

    log.warning('scheduling reminder events...')

    agencies = [g.db.agencies.find_one({'name':agcy})] if agcy else g.db.agencies.find()
    n_success = n_fails = 0
    evnt_ids = []

    for agency in agencies:
        agcy = agency['name']

        if not for_date:
            days_ahead = int(agency['scheduler']['notify']['delta_days'])
            for_date = date.today() + timedelta(days=days_ahead)

        date_str = for_date.strftime('%m-%d-%Y')
        blocks = []

        for key in agency['cal_ids']:
            blocks += cal.get_blocks(
                agency['cal_ids'][key],
                datetime.combine(for_date,time(8,0)),
                datetime.combine(for_date,time(9,0)),
                get_keys('google',agcy=agcy)['oauth'])

        if len(blocks) == 0:
            log.info('no blocks on %s (%s)', date_str, agcy)
            continue
        else:
            log.info('%s events on %s: %s (%s)',
                len(blocks), date_str, ", ".join(blocks), agcy)

        for block in blocks:
            try:
                evnt_id = pickups.create_reminder(agcy, block, for_date)
            except EtapError as e:
                n_fails +=1
                log.error('failed to create %s reminder (desc: %s)', block, str(e))
                log.debug('',exc_info=True)
                continue
            else:
                n_success +=1
                evnt_ids.append(str(evnt_id))
                log.debug('%s reminder event created', block)

    log.warning('created %s events successfully, %s failures', n_success, n_fails)
    return json.dumps(evnt_ids)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def skip_pickup(self, evnt_id=None, acct_id=None, **rest):
    '''User has opted out of a pickup via sms/voice/email noification.
    Run is_valid() before calling this function.
    @acct_id: _id from db.accounts, not eTap account id
    '''

    # Cancel any pending parent notifications

    result = g.db.notifics.update_many(
        {'acct_id':oid(acct_id), 'evnt_id':oid(evnt_id), 'tracking.status':'pending'},
        {'$set':{'tracking.status':'cancelled'}})
    acct = g.db.accounts.find_one_and_update(
        {'_id':oid(acct_id)},
        {'$set': {'opted_out': True}})
    evnt = g.db.events.find_one({'_id':oid(evnt_id)})

    if not evnt or not acct:
        msg = 'evnt/acct not found (evnt_id=%s, acct_id=%s' %(evnt_id,acct_id)
        log.error(msg)
        raise Exception(msg)

    log.info('<%s> opted out of pickup', (acct['email'] or acct['phone']))

    try:
        call(
            'skip_pickup',
            get_keys('etapestry',agcy=evnt['agency']),
            data={
                'acct_id': acct['udf']['etap_id'],
                'date': acct['udf']['pickup_dt'].strftime('%d/%m/%Y'),
                'next_pickup': to_local(
                    acct['udf']['future_pickup_dt'],
                    to_str='%d/%m/%Y')})
    except EtapError as e:
        log.error("etap error, desc='%s'", str(e))

    if not acct.get('email'):
        return 'success'

    try:
        body = render_template(
            'email/%s/no_pickup.html' % acct['agency'],
			to=acct['email'],
			account=to_local(obj=acct, to_str='%B %d %Y'))
    except Exception as e:
        log.error('render error: %s', str(e))
    else:
        mailgun.send(
            acct['email'],
            'Thanks for Opting Out',
            body,
            get_keys('mailgun',agcy=acct['agency']),
            v={'type':'opt_out', 'agcy':acct['agency']})

    return 'success'
