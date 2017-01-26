'''app.notify.pus'''
import logging, json, os
from twilio import twiml
from flask import g, request
from datetime import time, timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId
from .. import get_keys, utils, parser, gcal
from app.etap import EtapError, get_query, get_udf, get_phone, get_prim_phone,\
ddmmyyyy_to_local_dt as to_dt
from . import events, email, sms, voice, triggers, accounts
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def create_reminder(agcy, block, _date):
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    Returns: evnt_id (ObjectID) on succcess, False otherwise
    '''

    try:
        accts = get_query(block, get_keys('etapestry',agcy=agcy))
    except EtapError as e:
        raise
    else:
        if len(accts) < 1:
            raise EtapError('eTap query for Block %s is empty' % block)

    # Create event + triggers

    evnt_id = events.add(agcy, block, _date, 'bpu')
    conf = get_keys('scheduler',agcy=agcy)['notify']['triggers']
    email_trig_id = triggers.add(
        evnt_id,
        'email',
        _date + timedelta(days=conf['email']['fire_days_delta']),
        time(conf['email']['fire_hour'], conf['email']['fire_min']))

    if parser.is_res(block):
        phone_trig_id = triggers.add(
            evnt_id,
            'voice_sms',
            _date + timedelta(days=conf['voice_sms']['fire_days_delta']),
            time(
                conf['voice_sms']['fire_hour'],
                conf['voice_sms']['fire_min']))

    # Create notifications

    for acct in accts:
        npu = get_udf('Next Pickup Date', acct).split('/')

        if len(npu) < 3:
            log.error('Account %s missing npu. Skipping.', acct['id'])
            continue

        acct_id = accounts.add(
            agcy,
            evnt_id,
            acct['name'],
            phone = get_prim_phone(acct),
            email = acct.get('email'),
            udf = {
                'etap_id': acct['id'],
                'status': get_udf('Status', acct),
                'block': get_udf('Block', acct),
                'driver_notes': get_udf('Driver Notes', acct),
                'office_notes': get_udf('Office Notes', acct),
                'pickup_dt': to_dt(get_udf('Next Pickup Date', acct))},
            nameFormat = acct['nameFormat'])

        # A. Either Voice or SMS notification

        if parser.is_res(block):
            if get_phone('Mobile', acct):
                on_send = {
                    'source': 'template',
                    'template': 'sms/%s/reminder.html' % agcy}

                sms.add(
                    evnt_id,
                    _date,
                    phone_trig_id,
                    acct_id, get_phone('Mobile', acct),
                    on_send,
                    None)

            elif get_phone('Voice', acct):
                on_answer = {
                    'source': 'template',
                    'template': 'voice/%s/reminder.html' % agcy}

                on_interact = {
                    'module': 'app.notify.pus',
                    'func': 'on_call_interact'}

                voice.add(
                    evnt_id,
                    _date,
                    phone_trig_id,
                    acct_id, get_phone('Voice', acct),
                    on_answer, on_interact)

        # B. Email notification

        subject = 'Your upcoming pickup'

        if acct.get('email'):
            on_send = {
                'template': 'email/%s/reminder.html' % agcy,
                'subject': subject}

            email.add(
                evnt_id,
                _date,
                email_trig_id,
                acct_id, acct.get('email'),
                on_send)

    find_all_scheduled_dates(str(evnt_id))

    return evnt_id

#-------------------------------------------------------------------------------
def find_all_scheduled_dates(evnt_id):
    '''Update all reminders for given job with their future pickup dates to
    relay to opt-outs
    @evnt_id: str of ObjectID
    '''

    log.info('Getting next pickups for notification event ID \'%s\'', str(evnt_id))

    cal_events = []
    block_dates = {}
    evnt_id = ObjectId(evnt_id)
    event = g.db['notific_events'].find_one({'_id':evnt_id})

    start = event['event_dt'] + timedelta(days=1)
    end = start + timedelta(days=110)
    oauth = get_keys('google',agcy=event['agency'])['oauth']
    cal_ids = get_keys('cal_ids',agcy=event['agency'])

    try:
        service = gcal.gauth(oauth)

        for key in cal_ids:
            cal_events += gcal.get_events(
                service,
                cal_ids[key],
                start,
                end)
    except Exception as e:
        log.error('%s', str(e))
        log.debug('', exc_info=True)
        raise

    log.debug('%i calendar events pulled', len(cal_events))

    # Search calendar events to find pickup date
    for cal_event in cal_events:
        block = cal_event['summary'].split(' ')[0]

        if block not in block_dates:
            dt = parse(cal_event['start']['date'] + " T08:00:00")
            block_dates[block] = utils.naive_to_local(dt)

    notific_list = g.db['notifics'].find({'evnt_id':evnt_id})

    # Update future pickups for every notification under this event
    npu = ''
    for notific in notific_list:
        try:
            acct = g.db['accounts'].find_one({'_id':notific['acct_id']})

            npu = next_scheduled_date(
              acct['udf']['block'],
              acct['udf']['office_notes'] or '',
              block_dates)

            if npu:
                g.db['accounts'].update_one(
                    {'_id':notific['acct_id']},
                    {'$set':{'udf.future_pickup_dt':npu}})
        except Exception as e:
            log.error('Assigning future_dt %s to acct_id %s: %s',
            str(npu), str(acct['_id']), str(e))

#-------------------------------------------------------------------------------
def next_scheduled_date(blocks, office_notes, block_dates):
    '''Given list of blocks, find next scheduled date
    @blocks: string of comma-separated block names
    '''

    block_list = blocks.split(', ')

    # Remove temporary blocks

    # TODO: Handle multiple RMV BLK strings in office_notes

    if office_notes:
        rmv = parser.block_to_rmv(office_notes)

        if rmv and rmv in block_list:
            block_list.remove(rmv)

    # Find all matching dates and sort chronologically to find solution
    dates = []

    for block in block_list:
        if block in block_dates:
            dates.append(block_dates[block])

    if len(dates) < 1:
        log.error("Coudn't find npu for %s. office_notes: %s", blocks,office_notes)
        return False

    dates.sort()

    return dates[0]

#-------------------------------------------------------------------------------
def is_valid(evnt_id, acct_id):
    '''@evnt_id, acct_id: bson.objectid strings'''

    if not ObjectId.is_valid(evnt_id) or not ObjectId.is_valid(acct_id):
        return False

    evnt = g.db.notific_events.find_one({'_id':ObjectId(evnt_id)})
    acct = g.db.accounts.find_one({'_id':ObjectId(acct_id)})

    if not evnt or not acct:
        return False

    return True

#-------------------------------------------------------------------------------
def on_call_interact(notific):

    response = twiml.Response()

    # Digit 1: Play live message
    if request.form['Digits'] == '1':
        response.say(
            voice.get_speak(
              notific,
              notific['on_answer']['template']),
            voice='alice')

        response.gather(
            action= '%s/notify/voice/play/interact.xml' % os.environ.get('BRAVO_HTTP_HOST'),
            method='POST',
            numDigits=1,
            timeout=10)

        response.say(
            voice.get_speak(
              notific,
              notific['on_answer']['template'],
              timeout=True),
            voice='alice')

        response.hangup()

        return response

    # Digit 2: Cancel pickup
    elif request.form['Digits'] == '2':
        from app.notify.tasks import skip_pickup

        skip_pickup.delay(
            (str(notific['evnt_id']), str(notific['acct_id'])))

        acct = g.db['accounts'].find_one({'_id':notific['acct_id']})
        dt = utils.tz_utc_to_local(acct['udf']['future_pickup_dt'])

        response.say(
            voice.get_speak(
                notific,
                notific['on_answer']['template']),
            voice='alice'
        )

        response.hangup()

        return response
    elif request.form['Digits'] == '3':
        response.say(
            voice.get_speak(
              notific,
              notific['on_answer']['template']),
            voice='alice')

        response.hangup()

        return response