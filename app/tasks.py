'''app.tasks'''

import logging
import os
import traceback as tb
from celery import Celery
import logging
from bson.objectid import ObjectId as oid

from . import db
from . import create_app, create_celery_app, \
        debug_handler, info_handler, error_handler, exception_handler

flask_app = create_app('app')
celery = create_celery_app(flask_app)

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)
logger.addHandler(error_handler)
logger.addHandler(info_handler)
logger.addHandler(debug_handler)
logger.addHandler(exception_handler)
logger.setLevel(logging.DEBUG)


@celery.task
def mod_environ(args):
    for key in args:
        os.environ[key] = args[key]

#-------------------------------------------------------------------------------
@celery.task
def build_routes():
    try:
        from app.routing import routes
        return routes.build_scheduled_routes()
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def monitor_triggers():
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

            logger.debug('trigger %s scheduled. firing.', str(trigger['_id']))

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
        logger.error('%s\n%s', str(e), tb.format_exc())
        return False

    return True

#-------------------------------------------------------------------------------
@celery.task
def cancel_pickup(evnt_id, acct_id):
    try:
        from app.notify import pickup_service

        return pickup_service.cancel_pickup(
            oid(evnt_id),
            oid(acct_id))
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def build_route(route_id, job_id=None):
    try:
        from app.routing import routes
        return routes.build_route(route_id, job_id=job_id)
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def add_signup(signup):
    try:
        from app import wsf
        return wsf.add_signup(signup)
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def fire_trigger(evnt_id, trig_id):
    try:
        from app.notify import triggers
        return triggers.fire(oid(evnt_id), oid(trig_id))
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task
def send_receipts(entries, etapestry_id):
    try:
        from app.main import receipts
        return receipts.process(entries, etapestry_id)
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())


#-------------------------------------------------------------------------------
@celery.task
def rfu(agency, note,
        a_id=None, npu=None, block=None, _date=None, name_addy=None):
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
    try:
        from app.notify import pickup_service
        from app import schedule
        from datetime import datetime, date, time, timedelta

        agency = 'vec'


        preschedule_days = db['agencies'].find_one({
            'name': agency}
        )['scheduler']['notify']['preschedule_by_days']

        _date = date.today() + timedelta(days=preschedule_days)

        blocks = []

        agency_conf = db['agencies'].find_one({'name':agency})

        for key in agency_conf['cal_ids']:
            blocks += schedule.get_blocks(
                agency_conf['cal_ids'][key],
                datetime.combine(_date,time(8,0)),
                datetime.combine(_date,time(9,0)),
                agency_conf['google']['oauth']
            )

        logger.info('%s: scheduling reminders for %s on %s',
            agency_conf['name'], blocks, _date.strftime('%b %-d'))

        for block in blocks:
            res = pickup_service.create_reminder_event(agency_conf['name'], block, _date)

            if res == False:
                logger.info("No reminders created for %s", block)

        logger.info('%s: Done scheduling reminders', agency_conf['name'])
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())

    return True

#-------------------------------------------------------------------------------
@celery.task
def update_sms_accounts():
    '''Verify that all accounts in upcoming residential routes with mobile
    numbers are set up to interact with SMS system'''

    from . import sms, schedule

    agency_name = 'vec'
    days_from_now = 3

    agency_settings = db['agencies'].find_one({'name':agency_name})

    # Get accounts scheduled on Residential routes 3 days from now
    accounts = schedule.get_accounts(
        agency_settings['etapestry'],
        agency_settings['cal_ids']['res'],
        agency_settings['google']['oauth'],
        days_from_now=days_from_now)

    if len(accounts) < 1:
        return False

    client = TwilioLookupsClient(
      account = agency_settings['twilio']['keys']['main']['sid'],
      token = agency_settings['twilio']['keys']['main']['auth_id']
    )

    for account in accounts:
        # A. Verify Mobile phone setup for SMS
        mobile = etap.get_phone('Mobile', account)

        if mobile:
            # Make sure SMS udf exists

            sms_udf = etap.get_udf('SMS', account)

            if not sms_udf:
                int_format = re.sub(r'[^0-9.]', '', mobile['number'])

                if int_format[0:1] != "1":
                    int_format = "+1" + int_format

                logger.info('Adding SMS field to Account %s', str(account['id']))

                try:
                    etap.call('modify_account', agency_settings['etapestry'], {
                      'id': account['id'],
                      'udf': {'SMS': int_format},
                      'persona': []
                    })
                except Exception as e:
                    logger.error('Error modifying account %s: %s', str(account['id']), str(e))
            # Move onto next account
            continue

        # B. Analyze Voice phone in case it's actually Mobile.
        voice = etap.get_phone('Voice', account)

        if not voice:
            continue

        int_format = re.sub(r'[^0-9.]', '', voice['number'])

        if int_format[0:1] != "1":
            int_format = "+1" + int_format

        try:
            info = client.phone_numbers.get(int_format, include_carrier_info=True)
        except Exception as e:
            logger.error('Carrier lookup error (Account %s): %s', str(account['id']), str(e))
            continue

        if info.carrier['type'] != 'mobile':
            continue

        # Found a Mobile number labelled as Voice
        # Update Persona and SMS udf

        logger.info('Acct #%s: Found mobile number. SMS ready.', str(account['id']))

        try:
            etap.call('modify_account', agency_settings['etapestry'], {
              'id': account['id'],
              'udf': {'SMS': info.phone_number},
              'persona': {
                'phones':[
                  {'type':'Mobile', 'number': info.national_format},
                  {'type':'Voice', 'number': info.national_format}
                ]
              }
            })
        except Exception as e:
            logger.error('Error modifying account %s: %s', str(account['id']), str(e))

    return True

#-------------------------------------------------------------------------------
@celery.task
def find_non_participants():
    '''Create RFU's for all non-participants on scheduled dates'''
    from app import schedule
    from app.main import non_participants
    from . import etap, gsheets
    from datetime import date

    agencies = db['agencies'].find({})

    for agency in agencies:
        try:
            logger.info('%s: Analyzing non-participants in 5 days...', agency['name'])

            accounts = schedule.get_accounts(
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

                gsheets.create_rfu(
                  agency['name'],
                  'Non-participant',
                  a_id = np['id'],
                  npu = npu,
                  block = etap.get_udf('Block', np),
                  _date = date.today().strftime('%-m/%-d/%Y')
                )
        except Exception as e:
            logger.error('%s\n%s', str(e), tb.format_exc())

