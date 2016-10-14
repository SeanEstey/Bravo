'''app.notify.pickup_service'''

import logging
import json
from flask import current_app, render_template
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId as oid
from bson import json_util

from .. import utils, block_parser, gcal, etap
from .. import db
from . import events, notifics, triggers
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def create_reminder_event(agency, block, _date):
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    '''

    agency_conf = db['agencies'].find_one({'name':agency})

    try:
        with open('app/templates/schemas/'+agency+'.json') as json_file:
          schemas = json.load(json_file)
    except Exception as e:
        logger.error(str(e))

    for event in schemas['notification_events']:
        if event['name'] == 'pickup_reminder':
            schema = event
            break

    try:
        etap_accts = etap.call(
            'get_query_accounts',
            agency_conf['etapestry'],
            data={
                'query':block,
                'query_category':agency_conf['etapestry']['query_category']
            }
        )['data']
    except Exception as e:
        logger.error('Failed retrieving accounts for %s: %s', block, str(e))
        return False

    if len(accounts) < 1:
        return False

    # Create event + triggers

    evnt_id = events.insert(agency, block, _date)

    trig_conf = agency_conf['scheduler']['notify']['triggers']

    email_trig_id = triggers.add(
        evnt_id,
        'email',
        trig_conf['email']['fire_date'],
        trig_conf['email']['fire_time'])

    phone_trig_id = triggers.add(
        evnt_id,
        'voice_sms',
        trig_conf['voice_sms']['fire_date'],
        trig_conf['voice_sms']['fire_time'])

    event_dt = utils.naive_to_local(datetime.combine(_date,time(8,0)))

    # Create notifications

    for acct_obj in etap_accts:

        logger.debug(json.dumps(acct_obj))

        npu = etap.get_udf('Next Pickup Date', acct_obj).split('/')

        if len(npu) < 3:
            logger.error('Account %s missing npu. Skipping.', acct_obj['id'])
            continue

        acct_id = accounts.add(
            agency,
            acct_obj['id'],
            acct_obj['name'],
            phone = etap.get_primary_phone(acct_obj),
            email = acct_obj.get('email'),
            udf = {
                'status': etap.get_udf('Status', acct_obj),
                'block': etap.get_udf('Block', acct_obj),
                'driver_notes': etap.get_udf('Driver Notes', acct_obj),
                'office_notes': etap.get_udf('Office Notes', acct_obj),
                'pickup_dt': etap.ddmmyyyy_to_local_dt(
                    etap.get_udf('Next Pickup Date', acct_obj)
                )
            }
        )

        # A. Either Voice or SMS notification

        if etap.get_phone('Mobile', acct_obj):
            on_send = {
                'source': 'template',
                'template': 'sms/%s/reminder.html' % agency}

            on_reply = {
                'module': 'pickup_service',
                'func': 'on_sms_reply'}

            sms.add(
                evnt_id, event_dt,
                phone_trig_id,
                acct_id, etap.get_phone('Mobile', acct_obj),
                on_send, on_reply)

        elif etap.get_phone('Voice', acct_obj):
            on_answer = {
                'source': 'template',
                'template': 'voice/%s/reminder.html' % agency}

            on_interact = {
                'module': 'pickup_service',
                'func': 'on_call_interact'}

            voice.add(
                evnt_id, event_dt,
                phone_trig_id,
                acct_id, etap.get_phone('Voice', acct_obj),
                on_answer, on_interact)

        # B. Email notification

        if acct_obj.get('email'):
            on_send = {
                'template': 'email/%s/reminder.html' % agency,
                'subject': 'Your upcoming Vecova Bottle Service pickup'}

            email.add(
                evnt_id, event_dt,
                email_trig_id,
                acct_id, acct_obj.get('email'),
                on_send)

    add_future_pickups(str(evnt_id))

    return True

#-------------------------------------------------------------------------------
def add_future_pickups(evnt_id):
    '''Update all reminders for given job with their future pickup dates to
    relay to opt-outs
    @evnt_id: str of ObjectID
    '''

    evnt_id = oid(evnt_id)

    logger.info('Getting next pickups for notification event ID \'%s\'', str(evnt_id))

    event = db['notific_events'].find_one({'_id':evnt_id})
    agency_conf = db['agencies'].find_one({'name':event['agency']})

    start = event['event_dt'] + timedelta(days=1)
    end = start + timedelta(days=110)
    cal_events = []

    try:
        service = gcal.gauth(agency_conf['google']['oauth'])

        for key in agency_conf['cal_ids']:
            cal_events += gcal.get_events(
                service,
                agency_conf['cal_ids'][key],
                start,
                end
            )
    except Exception as e:
        logger.error('%s', str(e))
        return str(e)

    logger.debug('%i calendar events pulled', len(cal_events))

    block_dates = {}

    # Search calendar events to find pickup date
    for cal_event in cal_events:
        block = cal_event['summary'].split(' ')[0]

        if block not in block_dates:
            dt = parse(cal_event['start']['date'] + " T08:00:00")
            block_dates[block] = utils.naive_to_local(dt)

    notific_list = db['notifics'].find({'evnt_id':evnt_id})

    logger.debug('block_dats: %s', json_util.dumps(block_dates, sort_keys=True,indent=4))

    # Update future pickups for every notification under this event
    npu = ''
    for notific in notific_list:
        try:
            acct = db['accounts'].find_one({'_id':notific['acct_id']})

            npu = get_next_pickup(
              acct['udf']['block'],
              acct['udf']['office_notes'] or '',
              block_dates
            )

            if npu:
                db['accounts'].update_one({'_id':notific['acct_id']}, {
                    '$set':{'udf.future_pickup_dt':npu}
                })
        except Exception as e:
            logger.error('Assigning future_dt %s to acct_id %s: %s',
            str(npu), str(acct['_id']), str(e))

#-------------------------------------------------------------------------------
def get_next_pickup(blocks, office_notes, block_dates):
    '''Given list of blocks, find next scheduled date
    @blocks: string of comma-separated block names
    '''

    block_list = blocks.split(', ')

    # Remove temporary blocks

    # TODO: Handle multiple RMV BLK strings in office_notes

    if office_notes:
        rmv = block_parser.block_to_rmv(office_notes)

        if rmv:
            block_list.remove(rmv)
            logger.info("Removed temp block %s from %s", rmv, str(block_list))

    # Find all matching dates and sort chronologically to find solution
    dates = []

    for block in block_list:
        if block in block_dates:
            dates.append(block_dates[block])

    if len(dates) < 1:
        logger.error("Coudn't find npu for %s. office_notes: %s", blocks,office_notes)
        return False

    dates.sort()

    logger.debug("npu for %s: %s", blocks, dates[0].strftime('%-m/%-d/%Y'))

    return dates[0]

#-------------------------------------------------------------------------------
def cancel_pickup(evnt_id, acct_id):
    '''Called via either SMS, voice, or email reminder. eTap API is slow so runs as Celery
    background task.
    @acct_id: db['accounts']['_id']
    '''

    logger.info('Cancelling pickup for \'%s\'', acct_id)

    # Cancel any pending parent notifications

    db['notifics'].update({
          'acct_id': acct_id,
          'evnt_id': evnt_id,
          'tracking.status': 'pending'
        },{
          '$set': {
            'tracking.status':'cancelled',
            'opted_out':True}
        },
        multi=True)

    acct = db['accounts'].find_one_and_update({
        '_id':acct_id},{
        '$set': {
          'udf.opted_out': True
      }})

    conf = db['agencies'].find_one({
        'name': db['notific_events'].find_one({
            '_id':evnt_id})['agency']})

    try:
        etap.call(
            'no_pickup',
            conf['etapestry'],
            data={
                'account': acct['etap_id'],
                'date': acct['udf']['pickup_dt'].strftime('%d/%m/%Y'),
                'next_pickup': utils.tz_utc_to_local(
                    acct['udf']['future_pickup_dt']
                ).strftime('%d/%m/%Y')
            })
    except Exception as e:
        logger.error("Error writing to eTap: %s", str(e))

    if not acct.get('email'):
        return True

    # Send confirmation email
    # Running via celery worker outside request context
    # Must create one for render_template() and set SERVER_NAME for
    # url_for() to generate absolute URLs
    with current_app.test_request_context():
        current_app.config['SERVER_NAME'] = current_app.config['PUB_URL']
        try:
            body = render_template(
                'email/%s/no_pickup.html' % conf['agency'],
                to = acct['email'],
                account = acct
            )
        except Exception as e:
            logger.error('Error rendering no_pickup email. %s', str(e))
            current_app.config['SERVER_NAME'] = None
            return False
        current_app.config['SERVER_NAME'] = None

    return True

#-------------------------------------------------------------------------------
def on_call_interact(notific, args):
    # TODO: import twilio module

    response = twilio.twiml.Response()

    # Digit 1: Repeat message
    if args.get('Digits') == '1':
        content = voice.get_speak(
          notific,
          notific['content']['template']['default']['file'])

        response.say(content, voice='alice')

        response.gather(
            numDigits=1,
            action=current_app.config['PUB_URL'] + '/notify/voice/play/interact.xml',
            method='POST')

        return voice

    # Digit 2: Cancel pickup
    elif args.get('Digits') == '2':
        from .. import tasks
        tasks.cancel_pickup.apply_async(
            (str(notific['evnt_id']), str(notific['acct_id'])),
            queue=current_app.config['DB']
        )

        acct = db['accounts'].find_one({'_id':notific['acct_id']})
        dt = utils.tz_utc_to_local(acct['udf']['future_pickup_dt'])

        response.say(
          'Thank you. Your next pickup will be on ' +\
          dt.strftime('%A, %B %d') + '. Goodbye',
          voice='alice'
        )
        response.hangup()

        return response


#-------------------------------------------------------------------------------
def on_sms_reply(notific, args):
    # TODO: import twilio module

    response = twilio.twiml.Response()
    return True

