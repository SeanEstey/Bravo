'''app.notify.tasks'''
import logging, os, pytz
from datetime import datetime, date, time, timedelta
from bson import ObjectId
from flask import g
from app.utils import bcolors
from app import get_keys, cal, celery, smart_emit
from . import email, sms, voice, pickups, triggers
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def monitor_triggers(self, **kwargs):
    output = []

    smart_emit('test', 'monitor triggers update')

    try:
        from app.notify import triggers, events

        ready = g.db.triggers.find({
            'status':'pending',
            'fire_dt':{
                '$lt':datetime.utcnow()}})

        for trigger in ready:
            log.debug('trigger %s scheduled. firing.', str(trigger['_id']))

            fire_trigger(trigger['_id'])

        pending = g.db.triggers.find({
            'status':'pending',
            'fire_dt': {
                '$gt':datetime.utcnow()}})

        for trigger in pending:
            delta = trigger['fire_dt'] - datetime.utcnow().replace(tzinfo=pytz.utc)

            output.append(
                '%s trigger pending in %s' %(trigger['type'], str(delta)[:-7]))
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())

    print '%s%s%s' %(bcolors.ENDC,output,bcolors.ENDC)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def fire_trigger(self, _id, **rest):
    '''Sends out all dependent sms/voice/email notifics messages
    '''

    errors = []
    status = ''
    fails = 0
    trigger = g.db.triggers.find_one(
        {'_id':ObjectId(_id)})
    event = g.db.notific_events.find_one(
        {'_id':trigger['evnt_id']})
    agcy = event['agency']

    log.info('%s---------- firing %s trigger for "%s" event ----------%s',
        bcolors.OKGREEN, trigger['type'], event['name'], bcolors.ENDC)

    if os.environ.get('BRAVO_SANDBOX_MODE') == 'True':
        log.info('sandbox mode detected.')
        log.info('simulating voice/sms msgs, re-routing emails')

    g.db.triggers.update_one(
        {'_id':ObjectId(_id)},
        {'$set': {
            'task_id': self.request.id,
            'status': 'in-progress',
            'errors': errors}})

    smart_emit('trigger_status',{
        'trig_id': str(_id), 'status': 'in-progress'})

    ready = g.db.notifics.find(
        {'trig_id':ObjectId(_id), 'tracking.status':'pending'})
    count = ready.count()

    for n in ready:
        try:
            if n['type'] == 'voice':
                status = voice.call(n,
                    get_keys('twilio',agcy=agcy),
                    get_keys('notifiy',agcy=agcy)['voice'])
            elif n['type'] == 'sms':
                status = sms.send(n, get_keys('twilio',agcy=agcy))
            elif n['type'] == 'email':
                status = email.send(n, get_keys('mailgun',agcy=agcy))
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

    g.db.triggers.update_one({'_id':ObjectId(_id)}, {
        '$set': {'status': 'fired', 'errors': errors}})

    smart_emit('trigger_status', {
        'trig_id': str(_id),
        'status': 'fired',
        'sent': count-fails-len(errors),
        'fails': fails,
        'errors': len(errors)})

    log.info('%s---------- queued: %s, failed: %s, errors: %s ----------%s',
        bcolors.OKGREEN, count-fails-len(errors), fails, len(errors),bcolors.ENDC)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def schedule_reminders(self, agcy=None, for_date=None, **rest):

    if agcy and for_date:
        agencies = [g.db.agencies.find_one({'name':agcy})]
    else:
        agencies = g.db.agencies.find({})

    for agency in agencies:
        agcy = agency['name']

        if not for_date:
            days_ahead = agency['scheduler']['notify']['preschedule_by_days']
            for_date = date.today() + timedelta(days=days_ahead)

        blocks = []

        for key in agency['scheduler']['notify']['cal_ids']:
            blocks += cal.get_blocks(
                agency['cal_ids'][key],
                datetime.combine(for_date,time(8,0)),
                datetime.combine(for_date,time(9,0)),
                agency['google']['oauth'])

        if len(blocks) == 0:
            log.info('[%s] no blocks scheduled on %s',
                agcy, for_date.strftime('%b %-d'))
            return 'no blocks scheduled'

        log.info('[%s] scheduling reminders for %s on %s',
            agcy, blocks, for_date.strftime('%b %-d'))

        n=0
        for block in blocks:
            try:
                pickups.create_reminder(agcy, block, for_date)
            except EtapError as e:
                log.error('Error creating reminder, agcy=%s, block=%s, msg="%s"',
                    agcy, block, str(e))
                log.debug('', exc_info=True)
                continue
            else:
                n+=1

        log.info('[%s] scheduled %s/%s reminder events', agcy, n, len(blocks))

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def skip_pickup(self, evnt_id, acct_id, **kwargs):
    '''Runs as a celery task (tasks.cancel_pickup) to update an accounts eTap
    fields to skip a pickup. The request originates from a SMS/Voice/Email
    notification. Run is_valid() before calling this function.

    @acct_id: _id from db.accounts, not eTap account id
    '''

    log.info('Cancelling pickup for \'%s\'', acct_id)

    # Cancel any pending parent notifications

    result = g.db.notifics.update_many({
          'acct_id': acct_id,
          'evnt_id': evnt_id,
          'tracking.status': 'pending'
        },
        {'$set':{'tracking.status':'cancelled'}})

    acct = g.db.accounts.find_one_and_update({
        '_id':acct_id},{
        '$set': {
          'opted_out': True
      }})

    evnt = g.db.notific_events.find_one({'_id':evnt_id})

    if not evnt or not acct:
        log.error(
            'event or acct not found (evnt_id=%s, a_id=%s)',
            str(evnt_id), str(acct_id))
        raise

    conf = g.db.agencies.find_one({'name': evnt['agency']})

    try:
        etap.call(
            'no_pickup',
            conf['etapestry'],
            data={
                'account': acct['udf']['etap_id'],
                'date': acct['udf']['pickup_dt'].strftime('%d/%m/%Y'),
                'next_pickup': utils.tz_utc_to_local(
                    acct['udf']['future_pickup_dt']
                ).strftime('%d/%m/%Y')
            })
    except Exception as e:
        log.error("Error writing to eTap: %s", str(e))

    if not acct.get('email'):
        return 'success'

    return 'success'

    '''
    # Send confirmation email
    # Running via celery worker outside request context
    # Must create one for render_template() and set SERVER_NAME for
    # url_for() to generate absolute URLs
    with current_app.test_request_context():
        try:
            body = render_template(
                'email/%s/no_pickup.html' % conf['name'],
                to = acct['email'],
                account = acct,
                http_host= os.environ.get('BRAVO_HTTP_HOST')
            )
        except Exception as e:
            log.error('Error rendering no_pickup email. %s', str(e))
            return False
    '''
