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
from bson.objectid import ObjectId as oid
from bson import json_util

from .. import utils, parser, gcal, etap
from .. import db
from . import events, email, sms, voice, triggers, accounts
logger = logging.getLogger(__name__)


class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def reminder_event(agency, block, _date):
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    Returns: evnt_id (ObjectID) on succcess, False otherwise
    '''

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
        logger.error(msg)
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
            logger.error('Account %s missing npu. Skipping.', acct_obj['id'])
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
            }
        )

        # A. Either Voice or SMS notification

        if parser.is_res(block):
            if etap.get_phone('Mobile', acct_obj):
                on_send = {
                    'source': 'template',
                    'template': 'sms/%s/reminder.html' % agency}

                on_reply = {
                    'module': 'app.notify.pus',
                    'func': 'on_sms_reply'}

                sms.add(
                    evnt_id,
                    _date,
                    phone_trig_id,
                    acct_id, etap.get_phone('Mobile', acct_obj),
                    on_send, on_reply)

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

        if acct_obj.get('email'):
            on_send = {
                'template': 'email/%s/reminder.html' % agency,
                'subject': 'Your upcoming Vecova Bottle Service pickup'}

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
        rmv = parser.block_to_rmv(office_notes)

        if rmv and rmv in block_list:
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

    db.notifics.update({
          'acct_id': acct_id,
          'evnt_id': evnt_id,
          'tracking.status': 'pending'
        },
        {'$set':{'tracking.status':'cancelled'}},
        multi=True)

    acct = db.accounts.find_one_and_update({
        '_id':acct_id},{
        '$set': {
          'opted_out': True
      }})

    conf = db.agencies.find_one(
        {'name': db.notific_events.find_one(
            {'_id':evnt_id})['agency']})

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
        logger.error("Error writing to eTap: %s", str(e))

    if not acct.get('email'):
        return True

    # Send confirmation email
    # Running via celery worker outside request context
    # Must create one for render_template() and set SERVER_NAME for
    # url_for() to generate absolute URLs
    with current_app.test_request_context():
        #current_app.config['SERVER_NAME'] = os.environ.get('BRAVO_HTTP_HOST')
        try:
            body = render_template(
                'email/%s/no_pickup.html' % conf['name'],
                to = acct['email'],
                account = acct,
                http_host= os.environ.get('BRAVO_HTTP_HOST')
            )
        except Exception as e:
            logger.error('Error rendering no_pickup email. %s', str(e))
            #current_app.config['SERVER_NAME'] = None
            return False
        #current_app.config['SERVER_NAME'] = None

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

#-------------------------------------------------------------------------------
def on_sms_reply(notific):

    logger.info('bpu reply handler')
    from .. import html

    account = db['accounts'].find_one({'_id':notific['acct_id']})
    conf = db['agencies'].find_one({'name': account['agency']})

    if notific['tracking']['reply'] == 'NOPICKUP':
        cancel_pickup(notific['evnt_id'], notific['acct_id'])

    # Send SMS reply followup

    try:
        client = TwilioRestClient(
            conf['twilio']['api']['sid'],
            conf['twilio']['api']['auth_id'])
    except twilio.TwilioRestException as e:
        e_msg = 'twilio REST error. %s' % str(e)
        logger.error(e_msg, exc_info=True)
        return e_msg

    acct = db['accounts'].find_one(
        {'_id': notific['acct_id']})

    try:
        body = render_template(
            'sms/%s/reminder.html' % acct['agency'],
            account = utils.formatter(
                acct,
                to_local_time=True,
                to_strftime="%A, %B %d",
                bson_to_json=True),
            notific = notific
        )
    except Exception as e:
        e_msg = 'error rendering SMS body. %s' % str(e)
        logger.error(e_msg, exc_info=True)
        return e_msg

    try:
        client.messages.create(
            body = html.clean_whitespace(body),
            to = notific['to'],
            from_ = conf['twilio']['sms']['number'],
            status_callback = '%s/notify/sms/status' % os.environ.get('BRAVO_HTTP_HOST'))
    except Exception as e:
        e_msg = 'error sending SMS to %s. %s' % (notific['to'], str(e))
        logger.error(e_msg, exc_info=True)
        return e_msg

    return 'OK'
