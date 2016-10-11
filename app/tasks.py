'''app.tasks'''

from celery import Celery
import logging
from bson.objectid import ObjectId

from . import db
from . import create_app, create_celery_app

flask_app = create_app('app')
celery = create_celery_app(flask_app)

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@celery.task
def build_routes():
    from app.routing import routes
    return routes.build_scheduled_routes()

#-------------------------------------------------------------------------------
@celery.task
def monitor_triggers():
    from app.notify import triggers
    return triggers.monitor_all()

#-------------------------------------------------------------------------------
@celery.task
def cancel_pickup(evnt_id, acct_id):
    from app.notify import pickup_service
    return pickup_service._cancel(evnt_id, acct_id)

#-------------------------------------------------------------------------------
@celery.task
def build_route(route_id, job_id=None):
    from app.routing import routes
    return routes.build_route(route_id, job_id=job_id)

#-------------------------------------------------------------------------------
@celery.task
def add_signup(signup):
    from app import wsf
    return wsf.add_signup(signup)

#-------------------------------------------------------------------------------
@celery.task
def fire_trigger(evnt_id, trig_id):
    from app.notify import triggers

    return triggers.fire(ObjectId(evnt_id), ObjectId(trig_id))

#-------------------------------------------------------------------------------
@celery.task
def send_receipts(entries, etapestry_id):
    from app.main import receipts

    return receipts.process(entries, etapestry_id)

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
    from app.notify import pickup_service
    from app import schedule
    from datetime import datetime, date, time, timedelta

    PRESCHEDULE_BY_DAYS = 6
    agency = 'vec'

    blocks = []
    _date = date.today() + timedelta(days=PRESCHEDULE_BY_DAYS)

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
                  account_number = np['id'],
                  next_pickup = npu,
                  block = etap.get_udf('Block', np),
                  date = date.today().strftime('%-m/%-d/%Y')
                )
        except Exception as e:
            logger.error('non-participation exception: %s', str(e))
            continue
