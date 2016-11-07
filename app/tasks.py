'''app.tasks'''

import logging
import os
import traceback as tb
from celery import Celery
from celery.task.control import revoke
import logging
from bson.objectid import ObjectId as oid

from . import db, bcolors
from . import create_app, create_celery_app, \
        debug_handler, info_handler, error_handler, exception_handler
from . import utils

flask_app = create_app('app')
celery = create_celery_app(flask_app)


from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)
logger.addHandler(error_handler)
logger.addHandler(info_handler)
logger.addHandler(debug_handler)
logger.addHandler(exception_handler)
logger.setLevel(logging.DEBUG)



#-------------------------------------------------------------------------------
def kill(task_id):
    logger.info('attempting to kill task_id %s', task_id)

    try:
        response = celery.control.revoke(task_id, terminate=True)
    except Exception as e:
        logger.error('revoke task error: %s', str(e))
        return False

    logger.info('revoke response: %s', str(response))

    return response

#-------------------------------------------------------------------------------
@celery.task
def mod_environ(args):
    for key in args:
        os.environ[key] = args[key]



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
        from app.notify import pus

        return pus.cancel_pickup(
            oid(evnt_id),
            oid(acct_id))
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())


#-------------------------------------------------------------------------------
@celery.task
def analyze_upcoming_routes(days):
    import bson.json_util
    from dateutil.parser import parse
    from datetime import datetime, date, time, timedelta
    import re
    from app import task_emit
    from . import gcal, etap, wsf

    agency = 'vec'
    conf = db.agencies.find_one({'name':agency})['routing']
    cal_ids = db.agencies.find_one({'name':agency})['cal_ids']
    oauth = db.agencies.find_one({'name':agency})['google']['oauth']

    today_dt = datetime.combine(date.today(), time())
    end_dt = today_dt + timedelta(days=int(days))
    events = []

    for _id in cal_ids:
        events += gcal.get_events(gcal.gauth(oauth), cal_ids[_id], today_dt, end_dt)

    events = sorted(events, key=lambda k: k['start']['date'])

    logger.info('%s events', len(events))

    n=0

    task_emit('analyze_routes', {'status':'in-progress'})

    for event in events:
        # yyyy-mm-dd format
        event_dt = parse(event['start']['date'])

        block = re.match(r'^((B|R)\d{1,2}[a-zA-Z]{1})', event['summary']).group(0)

        if db.routes.find_one({'date':event_dt, 'block': block, 'agency':agency}):
            continue

        # Build route metadata

        # 1.a Let's grab info from eTapestry
        etap_conf = db.agencies.find_one({'name':agency})['etapestry']

        try:
            a = etap.call(
              'get_query_accounts',
              etap_conf,
              {'query':block, 'query_category':etap_conf['query_category']}
            )
        except Exception as e:
            logger.error('Error retrieving accounts for query %s', block)

        if 'count' not in a:
            logger.error('No accounts found in query %s', block)
            continue

        num_dropoffs = 0
        num_booked = 0

        event_d = event_dt.date()

        for account in a['data']:
            npu = etap.get_udf('Next Pickup Date', account)

            if npu == '':
                continue

            npu_d = etap.ddmmyyyy_to_date(npu)

            if npu_d == event_d:
                num_booked += 1

            if etap.get_udf('Status', account) == 'Dropoff':
                num_dropoffs += 1

        postal = re.sub(r'\s', '', event['location']).split(',')

        # TODO: move resolve_depot into depots.py module
        if len(conf['locations']['depots']) > 1:
            depot = wsf.resolve_depot(block, postal)
        else:
            depot = conf['locations']['depots'][0]

        _route = {
          'block': block,
          'date': event_dt,
          'agency': agency,
          'status': 'pending',
          'postal': re.sub(r'\s', '', event['location']).split(','),
          'depot': depot,
          'driver': conf['drivers'][0], # default driver
          'orders': num_booked,
          'block_size': len(a['data']),
          'dropoffs': num_dropoffs
        }

        db['routes'].insert_one(_route)
        logger.info(_route)

        # Send it to the client
        task_emit(
            'add_route_metadata',
            data=utils.formatter(
                _route,
                to_strftime=True,
                bson_to_json=True)
        )

        n+=1

    task_emit('analyze_routes', {'status':'completed'})

    logger.info('%s routes analyzed', n)

    return True

#-------------------------------------------------------------------------------
@celery.task
def build_route(route_id, job_id=None):
    try:
        from app.routing import routes
        return routes.build_route(str(route_id), job_id=job_id)
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())

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
def add_signup(signup):
    try:
        from app import wsf
        return wsf.add_signup(signup)
    except Exception as e:
        logger.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def fire_trigger(self, evnt_id, trig_id):
    logger.debug('trigger task_id: %s', self.request.id)

    # Store celery task_id in case we need to kill it
    db.triggers.update_one({
        '_id':oid(trig_id)},
        {'$set':{'task_id':self.request.id}})

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
    from app.notify import pus
    from app import schedule
    from datetime import datetime, date, time, timedelta

    agency = 'vec'
    agency_conf = db['agencies'].find_one({'name':agency})
    _date = date.today() + timedelta(
        days=agency_conf['scheduler']['notify']['preschedule_by_days'])

    blocks = []

    for key in agency_conf['cal_ids']:
        blocks += schedule.get_blocks(
            agency_conf['cal_ids'][key],
            datetime.combine(_date,time(8,0)),
            datetime.combine(_date,time(9,0)),
            agency_conf['google']['oauth']
        )

    if len(blocks) == 0:
        logger.info(
            '[%s] no blocks scheduled on %s',
            agency_conf['name'], _date.strftime('%b %-d'))
        return True

    logger.info(
        '[%s] scheduling reminders for %s on %s',
        agency_conf['name'], blocks, _date.strftime('%b %-d'))

    n=0
    for block in blocks:
        try:
            pus.reminder_event(agency_conf['name'], block, _date)
        except EtapError as e:
            continue
        else:
            n+=1

    logger.info(
        '[%s] scheduled %s/%s reminder events', 
        agency_conf['name'], n, len(blocks)
    )

    return True

#-------------------------------------------------------------------------------
@celery.task
def update_sms_accounts(days_delta=None):
    '''Verify that all accounts in upcoming residential routes with mobile
    numbers are set up to interact with SMS system'''

    import re
    from . import schedule, etap
    from twilio.rest.lookups import TwilioLookupsClient

    agencies = db.agencies.find({})

    for agency in agencies:
        if days_delta == None:
            days_delta = 3
        else:
            days_delta = int(days_delta)

        #agency_settings = db['agencies'].find_one({'name':agency_name})

        # Get accounts scheduled on Residential routes 3 days from now
        accounts = schedule.get_accounts(
            agency['etapestry'],
            agency['cal_ids']['res'],
            agency['google']['oauth'],
            days_from_now=days_delta)

        if len(accounts) < 1:
            return False

        client = TwilioLookupsClient(
          account = agency['twilio']['api']['sid'],
          token = agency['twilio']['api']['auth_id']
        )

        n = 0

        for account in accounts:
            # A. Verify Mobile phone setup for SMS
            mobile = etap.get_phone('Mobile', account)

            if mobile:
                # Make sure SMS udf exists

                sms_udf = etap.get_udf('SMS', account)

                if not sms_udf:
                    int_format = re.sub(r'[^0-9.]', '', mobile)

                    if int_format[0:1] != "1":
                        int_format = "+1" + int_format

                    logger.info('Adding SMS field to Account %s', str(account['id']))

                    try:
                        etap.call('modify_account', agency['etapestry'], {
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

            if not voice or voice == '':
                continue

            int_format = re.sub(r'[^0-9.]', '', voice)

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
                etap.call('modify_account', agency['etapestry'], {
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

            n+=1

        logger.info('%s ---------- updated %s accounts for mobile-ready ----------%s',
                    bcolors.OKGREEN, str(n), bcolors.ENDC)

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

