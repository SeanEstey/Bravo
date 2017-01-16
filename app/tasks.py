'''app.tasks'''
import logging
import os
from time import sleep
import traceback as tb
from celery.task.control import revoke
from celery.signals import task_success
from celery.utils.log import get_task_logger
from bson.objectid import ObjectId as oid
from flask_socketio import SocketIO
from etap import EtapError
from utils import bcolors, print_vars
from flask import current_app, g, request, has_app_context,has_request_context
from . import mongodb, get_db, utils, create_app, celery_app, deb_hand,\
inf_hand, err_hand, exc_hand

log = get_task_logger(__name__)
log.addHandler(err_hand)
log.addHandler(inf_hand)
log.addHandler(deb_hand)
log.addHandler(exc_hand)
log.setLevel(logging.DEBUG)
celery = celery_app(create_app('app', kv_sess=False))
c_db_client = mongodb.create_client(connect=False, auth=False)
c_sio_app = SocketIO(message_queue='amqp://')

#-------------------------------------------------------------------------------
@task_success.connect
def task_complete(result, **kwargs):
    log.debug('success: %s', kwargs['sender'].name.split('.')[-1])

#-------------------------------------------------------------------------------
def task_init():
    #log.debug(
    #    'Worker | app_ctx=%s | req_ctx=%s',
    #    has_app_context(), has_request_context())

    if has_app_context():
        mongodb.authenticate(c_db_client)
        g.db = c_db_client['bravo']
    else:
        log.debug('no app context')
        return False

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def mod_environ(self, *args, **kwargs):
    task_init()

    for idx, arg in enumerate(args):
        for k in arg:
            os.environ[k] = arg[k]

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def analyze_upcoming_routes(self, *args, **kwargs):
    task_init()
    sleep(3)
    c_sio_app.emit('analyze_routes', {'status':'in-progress'})

    from app.routing.schedule import analyze_upcoming
    try:
        analyze_upcoming('vec', 5)
    except Exception as e:
        log.error(str(e))
        log.debug(str(e), exc_info=True)

    c_sio_app.emit('analyze_routes', {'status':'completed'})
    return True

#-------------------------------------------------------------------------------
@celery.task
def monitor_triggers():
    task_init()
    try:
        from app.notify import triggers, events
        from datetime import datetime, timedelta
        import pytz

        ready = db['triggers'].find({
            'status':'pending',
            'fire_dt':{
                '$lt':datetime.utcnow()}})

        for trigger in ready:
            event = events.get(trigger['evnt_id'])

            log.debug('trigger %s scheduled. firing.', str(trigger['_id']))

            triggers.fire(trigger['evnt_id'], trigger['_id'])

        pending = db['triggers'].find({
            'status':'pending',
            'fire_dt': {
                '$gt':datetime.utcnow()}})

        for trigger in pending:


            delta = trigger['fire_dt'] - datetime.utcnow().replace(tzinfo=pytz.utc)

            print '%s trigger pending in %s' %(
                trigger['type'], str(delta)[:-7])
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())
        return False

    return True

#-------------------------------------------------------------------------------
@celery.task
def cancel_pickup(evnt_id, acct_id):
    task_init()
    try:
        from app.notify import pus

        return pus.cancel_pickup(
            oid(evnt_id),
            oid(acct_id))
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def build_scheduled_routes():
    '''Route orders for today's Blocks and build Sheets
    '''

    task_init()
    from app.routing import main
    from app.routing.schedule import analyze_upcoming
    from datetime import datetime, date, time
    from time import sleep

    agencies = db.agencies.find({})

    for agency in agencies:
        analyze_upcoming(agency['name'], 3)

        _routes = db.routes.find({
          'agency': agency['name'],
          'date': utils.naive_to_local(
            datetime.combine(
                date.today(),
                time(0,0,0)))
        })

        log.info(
          '%s: -----Building %s routes for %s-----',
          agency['name'], _routes.count(), date.today().strftime("%A %b %d"))

        successes = 0
        fails = 0

        for route in _routes:
            r = main.build(str(route['_id']))

            if not r:
                fails += 1
                log.error('Error building route %s', route['block'])
            else:
                successes += 1

            sleep(2)

        log.info(
            '%s: -----%s Routes built. %s failures.-----',
            agency['name'], successes, fails)



#-------------------------------------------------------------------------------
@celery.task
def build_route(route_id, job_id=None):
    task_init()
    try:
        from app.routing import main
        return main.build(str(route_id), job_id=job_id)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def add_signup(signup):
    task_init()
    try:
        from app import wsf
        return wsf.add_signup(signup)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def fire_trigger(self, evnt_id, trig_id):
    task_init()

    log.debug('trigger task_id: %s', self.request.id)

    db = get_db()

    # Store celery task_id in case we need to kill it
    db.triggers.update_one({
        '_id':oid(trig_id)},
        {'$set':{'task_id':self.request.id}})

    try:
        from app.notify import triggers
        return triggers.fire(oid(evnt_id), oid(trig_id))
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def send_receipts(entries, etapestry_id):
    task_init()
    try:
        from app.main import receipts
        return receipts.process(entries, etapestry_id)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())


#-------------------------------------------------------------------------------
@celery.task
def rfu(agency, note,
        a_id=None, npu=None, block=None, _date=None, name_addy=None):
    task_init()
    from app import gsheets

    return gsheets.create_rfu(
        agency,
        note,
        a_id=a_id,
        npu=npu,
        block=block,
        _date=_date,
        name_addy=name_addy
    )

#-------------------------------------------------------------------------------
@celery.task
def schedule_reminders():
    task_init()
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
            return True

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

    return True

#-------------------------------------------------------------------------------
@celery.task
def update_sms_accounts(agency_name=None, days_delta=None):
    '''Verify that all accounts in upcoming residential routes with mobile
    numbers are set up to interact with SMS system'''

    task_init()
    import re
    from . import cal
    from app.main import sms

    if days_delta == None:
        days_delta = 3
    else:
        days_delta = int(days_delta)

    if agency_name:
        conf = db.agencies.find_one({'name':agency_name})

        accounts = cal.get_accounts(
            conf['etapestry'],
            conf['cal_ids']['res'],
            conf['google']['oauth'],
            days_from_now=days_delta)

        if len(accounts) < 1:
            return False

        r = sms.enable(agency_name, accounts)

        log.info('%s --- updated %s accounts for SMS. discovered %s mobile numbers ---%s',
                    bcolors.OKGREEN, r['n_sms'], r['n_mobile'], bcolors.ENDC)
    else:
        agencies = db.agencies.find({})

        for agency in agencies:
            # Get accounts scheduled on Residential routes 3 days from now
            accounts = cal.get_accounts(
                agency['etapestry'],
                agency['cal_ids']['res'],
                agency['google']['oauth'],
                days_from_now=days_delta)

            if len(accounts) < 1:
                return False

            r = sms.enable(agency['name'], accounts)

            log.info('%s --- updated %s accounts for SMS. discovered %s mobile numbers ---%s',
                        bcolors.OKGREEN, r['n_sms'], r['n_mobile'], bcolors.ENDC)

    return True

#-------------------------------------------------------------------------------
@celery.task
def enable_all_accounts_sms():
    task_init()
    import etap

    agencies = db.agencies.find({})

    for agency in agencies:
        try:
            accounts = etap.call(
                'get_query_accounts',
                agency['etapestry'], {
                    'query_category': agency['config']['bpu']['accounts']['etapestry']['category'],
                    'query': agency['config']['bpu']['accounts']['etapestry']['query']
                }
            )
        except Exception as e:
            log.error('Error retrieving master account list. %s', str(e))
            return False

        subset = accounts[0:10]

        n = sms.enable(agency['name'], subset)

        log.info('enabled %s accounts for SMS', n)


#-------------------------------------------------------------------------------
@celery.task
def find_non_participants():
    '''Create RFU's for all non-participants on scheduled dates'''
    task_init()
    from app import cal
    from app.main import non_participants
    from . import etap, gsheets
    from datetime import date

    agencies = db['agencies'].find({})

    for agency in agencies:
        try:
            log.info('%s: Analyzing non-participants in 5 days...', agency['name'])

            accounts = cal.get_accounts(
                agency['etapestry'],
                agency['cal_ids']['res'],
                agency['google']['oauth'],
                days_from_now=5)

            if len(accounts) < 1:
                continue

            nps = non_participants.find(agency['name'], accounts)

            for np in nps:
                npu = etap.get_udf('Next Pickup Date', np)

                if len(npu.split('/')) == 3:
                    npu = etap.ddmmyyyy_to_mmddyyyy(npu)

                etap.call(
                    'modify_account',
                    agency['etapestry'], {
                        'id': np['id'],
                        'udf': {
                            'Office Notes': etap.get_udf('Office Notes', np) +\
                            '\n' + date.today().strftime('%b %-d %Y') + \
                            ': flagged as non-participant ' +\
                            ' (no collection in ' +\
                            str(agency['config']['non_participant_days']) + ' days)'

                        },
                        'persona':{}
                    }
                )

                gsheets.create_rfu(
                  agency['name'],
                  'Non-participant. No collection in %s days.' % agency['config']['non_participant_days'],
                  a_id = np['id'],
                  npu = npu,
                  block = etap.get_udf('Block', np),
                  _date = date.today().strftime('%-m/%-d/%Y'),
                  driver_notes = etap.get_udf('Driver Notes', np),
                  office_notes = etap.get_udf('Office Notes', np)
                )
        except Exception as e:
            log.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def update_maps(agency=None, emit_status=False):
    task_init()
    from app.booker import geo

    if agency:
        geo.update_maps(agency, emit_status)
    else:
        for agency in db.agencies.find({}):
            geo.update_maps(agency['name'], emit_status)

#-------------------------------------------------------------------------------
def kill(task_id):
    log.info('attempting to kill task_id %s', task_id)

    try:
        response = celery.control.revoke(task_id, terminate=True)
    except Exception as e:
        log.error('revoke task error: %s', str(e))
        return False

    log.info('revoke response: %s', str(response))

    return response

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def test_trig(self, *args, **kwargs):
    task_init()

    from app.notify import triggers
    triggers.context_test()

