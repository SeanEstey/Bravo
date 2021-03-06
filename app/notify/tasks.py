'''app.notify.tasks'''
import json, os, pytz
from os import environ as env
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from bson import ObjectId as oid
from flask import g, render_template
from app import get_keys, celery #, smart_emit
from app.lib.dt import to_local
from app.lib import mailgun
from app.main import schedule
from app.main.parser import is_bus
from app.main.etapestry import call, EtapError
from . import email, events, sms, voice, pickups, triggers
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def monitor_triggers(self, **kwargs):

    ready = g.db.triggers.find({
        'status':'pending',
        'fire_dt':{
            '$lt':datetime.utcnow()}})

    for trigger in ready:
        evnt = g.db.events.find_one({'_id':trigger['evnt_id']})
        g.group = evnt['agency']

        log.debug('Firing event trigger for %s', evnt['name'], extra={'trigger_id':str(trigger['_id'])})

        try:
            fire_trigger(trigger['_id'])
        except Exception as e:
            log.exception('Error firing event trigger for %s', evnt['name'])

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

    status = ''
    n_errors = 0
    trig = g.db.triggers.find_one({'_id':oid(_id)})
    event = g.db.events.find_one({'_id':trig['evnt_id']})
    g.group = event['agency']

    g.db.triggers.update_one(
        {'_id':oid(_id)},
        {'$set': {'task_id':self.request.id, 'status':'in-progress'}})

    events.update_status(trig['evnt_id'])

    ready = g.db.notifics.find(
        {'trig_id':oid(_id), 'tracking.status':'pending'})
    count = ready.count()

    log.info('Sending notifications for event %s...', event['name'],
        extra={'type':trig['type'], 'n_total':count})

    #smart_emit('trigger_status',{
    #    'trig_id': str(_id), 'status': 'in-progress'})

    if env['BRV_SANDBOX'] == 'True':
        log.info('sandbox: simulating voice/sms, rerouting emails')

    for n in ready:
        try:
            if n['type'] == 'voice':
                status = voice.call(n, get_keys('twilio'))
            elif n['type'] == 'sms':
                status = sms.send(n, get_keys('twilio'))
            elif n['type'] == 'email':
                status = email.send(n, get_keys('mailgun'))
        except Exception as e:
            n_errors +=1
            status = 'error'
            log.exception('Error sending notification to %s', n['to'],
                extra={'type':n['type']})
        else:
            if status == 'failed':
                n_errors += 1
        finally:
            pass
            #smart_emit('notific_status', {
            #    'notific_id':str(n['_id']), 'status':status})

    g.db.triggers.update_one({'_id':oid(_id)}, {'$set': {'status': 'fired'}})

    '''smart_emit('trigger_status', {
        'trig_id': str(_id),
        'status': 'fired',
        'sent': count - n_errors,
        'errors': n_errors})'''

    log.info('%s/%s notifications sent for event %s', count - n_errors, count, event['name'],
        extra={'type':trig['type'], 'n_total':count, 'n_errors':n_errors})

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def schedule_reminders(self, group=None, for_date=None, **rest):

    if for_date:
        for_date = parse(for_date).date()

    groups = [g.db['groups'].find_one({'name':group})] if group else g.db['groups'].find()
    evnt_ids = []

    for group_ in groups:
        n_success = n_fails = 0
        g.group = group_['name']
        log.info('Scheduling notification events...')

        days_ahead = int(group_['notify']['sched_delta_days'])
        on_date = date.today() + timedelta(days=days_ahead) if not for_date else for_date
        date_str = on_date.strftime('%m-%d-%Y')
        blocks = []

        for key in group_['cal_ids']:
            blocks += schedule.get_blocks(
                group_['cal_ids'][key],
                datetime.combine(on_date,time(8,0)),
                datetime.combine(on_date,time(9,0)),
                get_keys('google')['oauth'])

        if len(blocks) == 0:
            log.debug('no blocks on %s', date_str)
            continue
        else:
            log.debug('%s events on %s: %s',
                len(blocks), date_str, ", ".join(blocks))

        for block in blocks:
            if is_bus(block) and group_['notify']['sched_business'] == False:
                continue

            try:
                evnt_id = pickups.create_reminder(g.group, block, on_date)
            except EtapError as e:
                n_fails +=1
                log.exception('Error creating notification event %s', block)
                continue
            else:
                n_success +=1
                evnt_ids.append(str(evnt_id))
                log.info('Created notification event %s', block)

        log.info('Created %s/%s scheduled notification events',
            n_success, n_success + n_fails)

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

    g.group = evnt['agency']

    log.info('%s opted out of pickup',
        acct.get('name') or acct.get('email'),
        extra={'event_name':evnt['name'], 'account_id':acct['udf']['etap_id']})

    try:
        call('skip_pickup', data={
            'acct_id': acct['udf']['etap_id'],
            'date': acct['udf']['pickup_dt'].strftime('%d/%m/%Y'),
            'next_pickup': to_local(
                acct['udf']['future_pickup_dt'],
                to_str='%d/%m/%Y')})
    except Exception as e:
        log.exception('Error calling skip_pickup')
        log.exception("Error updating account %s",
            acct.get('name') or acct.get('email'),
            extra={'account_id': acct['udf']['etap_id']})

    if not acct.get('email'):
        return 'success'

    try:
        body = render_template(
            'email/%s/no_pickup.html' % g.group,
			to=acct['email'],
			account=to_local(obj=acct, to_str='%B %d %Y'))
    except Exception as e:
        log.exception('Error rendering no_pickup template')
        raise
    else:
        mailgun.send(
            acct['email'],
            'Thanks for Opting Out',
            body,
            get_keys('mailgun'),
            v={'type':'opt_out', 'group':g.group})

    return 'success'
