'''app.notify.pus'''

import logging
import os
import json
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import current_app, render_template, request
from flask_login import current_user
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId
from bson import json_util
from .. import get_db, utils, parser, gcal, etap
from . import events, email, sms, voice, triggers, accounts
log = logging.getLogger(__name__)


class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def reminder_event(agency, block, _date):
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    Returns: evnt_id (ObjectID) on succcess, False otherwise
    '''

    db = get_db()

    agency_conf = db['agencies'].find_one({'name':agency})

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
        msg = 'Failed to retrieve query "%s". Details: %s' % (block, str(e))
        log.error(msg)
        raise EtapError(msg)
    else:
        if len(etap_accts) < 1:
            raise EtapError('eTap query for Block %s is empty' % block)

    # Create event + triggers

    evnt_id = events.add(agency, block, _date, 'bpu')

    trig_conf = agency_conf['scheduler']['notify']['triggers']

    email_trig_id = triggers.add(
        evnt_id,
        'email',
        _date + timedelta(days=trig_conf['email']['fire_days_delta']),
        time(
            trig_conf['email']['fire_hour'],
            trig_conf['email']['fire_min'])
    )

    if parser.is_res(block):
        phone_trig_id = triggers.add(
            evnt_id,
            'voice_sms',
            _date + timedelta(days=trig_conf['voice_sms']['fire_days_delta']),
            time(
                trig_conf['voice_sms']['fire_hour'],
                trig_conf['voice_sms']['fire_min'])
        )

    # Create notifications

    for acct_obj in etap_accts:
        npu = etap.get_udf('Next Pickup Date', acct_obj).split('/')

        if len(npu) < 3:
            log.error('Account %s missing npu. Skipping.', acct_obj['id'])
            continue

        acct_id = accounts.add(
            agency,
            evnt_id,
            acct_obj['name'],
            phone = etap.get_primary_phone(acct_obj),
            email = acct_obj.get('email'),
            udf = {
                'etap_id': acct_obj['id'],
                'status': etap.get_udf('Status', acct_obj),
                'block': etap.get_udf('Block', acct_obj),
                'driver_notes': etap.get_udf('Driver Notes', acct_obj),
                'office_notes': etap.get_udf('Office Notes', acct_obj),
                'pickup_dt': etap.ddmmyyyy_to_local_dt(
                    etap.get_udf('Next Pickup Date', acct_obj)
                )
            },
            nameFormat = acct_obj['nameFormat']
        )

        # A. Either Voice or SMS notification

        if parser.is_res(block):
            if etap.get_phone('Mobile', acct_obj):
                on_send = {
                    'source': 'template',
                    'template': 'sms/%s/reminder.html' % agency}

                sms.add(
                    evnt_id,
                    _date,
                    phone_trig_id,
                    acct_id, etap.get_phone('Mobile', acct_obj),
                    on_send,
                    None)

            elif etap.get_phone('Voice', acct_obj):
                on_answer = {
                    'source': 'template',
                    'template': 'voice/%s/reminder.html' % agency}

                on_interact = {
                    'module': 'app.notify.pus',
                    'func': 'on_call_interact'}

                voice.add(
                    evnt_id,
                    _date,
                    phone_trig_id,
                    acct_id, etap.get_phone('Voice', acct_obj),
                    on_answer, on_interact)

        # B. Email notification

        subject = 'Your upcoming pickup'

        if acct_obj.get('email'):
            on_send = {
                'template': 'email/%s/reminder.html' % agency,
                'subject': subject}

            email.add(
                evnt_id,
                _date,
                email_trig_id,
                acct_id, acct_obj.get('email'),
                on_send)

    add_future_pickups(str(evnt_id))

    return evnt_id

#-------------------------------------------------------------------------------
def add_future_pickups(evnt_id):
    '''Update all reminders for given job with their future pickup dates to
    relay to opt-outs
    @evnt_id: str of ObjectID
    '''

    evnt_id = ObjectId(evnt_id)

    log.info('Getting next pickups for notification event ID \'%s\'', str(evnt_id))

    db = get_db()

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
        log.error('%s', str(e))
        return str(e)

    log.debug('%i calendar events pulled', len(cal_events))

    block_dates = {}

    # Search calendar events to find pickup date
    for cal_event in cal_events:
        block = cal_event['summary'].split(' ')[0]

        if block not in block_dates:
            dt = parse(cal_event['start']['date'] + " T08:00:00")
            block_dates[block] = utils.naive_to_local(dt)

    notific_list = db['notifics'].find({'evnt_id':evnt_id})

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
            log.error('Assigning future_dt %s to acct_id %s: %s',
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

    evnt = db.notific_events.find_one({'_id':ObjectId(evnt_id)})
    acct = db.accounts.find_one({'_id':ObjectId(acct_id)})

    if not evnt or not acct:
        return False

    return True



#-------------------------------------------------------------------------------
def on_call_interact(notific):

    response = twiml.Response()
    db = get_db()

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
        from .. import tasks
        tasks.cancel_pickup.apply_async(
            (str(notific['evnt_id']), str(notific['acct_id'])),
            queue=current_app.config['DB']
        )

        acct = db['accounts'].find_one({'_id':notific['acct_id']})
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
