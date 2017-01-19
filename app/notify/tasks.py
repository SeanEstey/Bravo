'''app.notify.tasks'''

import logging
from datetime import datetime, timedelta
import pytz
from bson import ObjectId
from flask import g
from app.utils import bcolors
from app.tasks import celery_sio, celery
from . import triggers
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def monitor_triggers(self, **kwargs):
    output = []

    try:
        from app.notify import triggers, events

        ready = g.db.triggers.find({
            'status':'pending',
            'fire_dt':{
                '$lt':datetime.utcnow()}})

        for trigger in ready:
            event = events.get(trigger['evnt_id'])

            log.debug('trigger %s scheduled. firing.', str(trigger['_id']))

            triggers.fire(trigger['evnt_id'], trigger['_id'])

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

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def fire_trigger(self, evnt_id, trig_id, **kwargs):
    log.debug('trigger task_id: %s', self.request.id)

    g.db.triggers.update_one({
        '_id':ObjectId(trig_id)},
        {'$set':{'task_id':self.request.id}})

    triggers.fire(ObjectId(evnt_id), ObjectId(trig_id))

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def schedule_reminders(self, *args, **kwargs):
    from app.notify import pus
    from app import cal
    from datetime import datetime, date, time, timedelta

    agencies = db.agencies.find({})

    for agency in agencies:
        _date = date.today() + timedelta(
            days=agency['scheduler']['notify']['preschedule_by_days'])

        blocks = []

        for key in agency['scheduler']['notify']['cal_ids']:
            blocks += cal.get_blocks(
                agency['cal_ids'][key],
                datetime.combine(_date,time(8,0)),
                datetime.combine(_date,time(9,0)),
                agency['google']['oauth']
            )

        if len(blocks) == 0:
            log.info(
                '[%s] no blocks scheduled on %s',
                agency['name'], _date.strftime('%b %-d'))
            return

        log.info(
            '[%s] scheduling reminders for %s on %s',
            agency['name'], blocks, _date.strftime('%b %-d'))

        n=0
        for block in blocks:
            try:
                pus.reminder_event(agency['name'], block, _date)
            except EtapError as e:
                continue
            else:
                n+=1

        log.info(
            '[%s] scheduled %s/%s reminder events',
            agency['name'], n, len(blocks)
        )

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def skip_pickup(self, *args, **kwargs):
    '''Runs as a celery task (tasks.cancel_pickup) to update an accounts eTap
    fields to skip a pickup. The request originates from a SMS/Voice/Email
    notification. Run is_valid() before calling this function.

    @acct_id: _id from db.accounts, not eTap account id
    '''

    evnt_id = args[0] # FIXME
    acct_id = args[1] # FIXME

    log.info('Cancelling pickup for \'%s\'', acct_id)

    db = get_db()

    # Cancel any pending parent notifications

    result = db.notifics.update_many({
          'acct_id': acct_id,
          'evnt_id': evnt_id,
          'tracking.status': 'pending'
        },
        {'$set':{'tracking.status':'cancelled'}})

    acct = db.accounts.find_one_and_update({
        '_id':acct_id},{
        '$set': {
          'opted_out': True
      }})

    evnt = db.notific_events.find_one({'_id':evnt_id})

    if not evnt or not acct:
        logger.error(
            'event or acct not found (evnt_id=%s, a_id=%s)',
            str(evnt_id), str(acct_id))
        return False

    conf = db.agencies.find_one({'name': evnt['agency']})

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
        return True

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
