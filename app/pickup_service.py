import logging
import json
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId
from bson import json_util

import utils
import block_parser
import scheduler
import etap
import notific_events
import notifications
import triggers
from app import app, db
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
#@celery_app.task
def schedule_reminder_events():
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    '''

    DAYS_IN_ADVANCE_TO_SCHEDULE = 6
    agency = 'vec'

    agency_conf = db['agencies'].find_one({'name':agency})

    blocks = []
    block_date = date.today() + timedelta(days=DAYS_IN_ADVANCE_TO_SCHEDULE)

    for key in agency_conf['cal_ids']:
        blocks += scheduler.get_blocks(
            agency_conf['cal_ids'][key],
            datetime.combine(block_date,time(8,0)),
            datetime.combine(block_date,time(9,0)),
            agency_conf['google']['oauth']
        )

    try:
        with open('app/templates/schemas/'+agency+'.json') as json_file:
          schemas = json.load(json_file)
    except Exception as e:
        logger.error(str(e))

    for event in schemas['notification_events']:
        if event['name'] == 'pickup_reminder':
            schema = event
            break

    for block in blocks:
        try:
            accounts = etap.call(
                'get_query_accounts',
                agency_conf['etapestry'],
                data={
                    'query':block,
                    'query_category':agency_conf['etapestry']['query_category']
                })['data']
        except Exception as e:
            logger.error('Error retrieving accounts for query %s', block)

        if len(accounts) < 1:
            continue

        # Create notification event and add triggers

        event_id = notific_events.add(agency, block, block_date)

        for conf in agency_conf['notifications']:
            _date = block_date + timedelta(days=conf['fire_days_delta'])
            _time = time(conf['fire_hour'], conf['fire_min'])

            if conf['type'] == 'sms':
                continue
            elif conf['type'] == 'voice':
                phone_trig_id = triggers.add(event_id, _date, _time, 'phone')
            elif conf['type'] == 'email':
                email_trig_id = triggers.add(event_id, _date, _time, 'email')

        event_dt = utils.naive_to_local(datetime.combine(block_date,time(8,0)))

        # Add notifications
        for account in accounts:
            logger.debug(json.dumps(account))

            npu = etap.get_udf('Next Pickup Date', account).split('/')

            if len(npu) < 3:
                logger.error('Account %s missing npu. Skipping.', account['id'])
                continue

            add_notification(event_id, event_dt, phone_trig_id, 'phone', account, schema)
            add_notification(event_id, event_dt, email_trig_id, 'email', account, schema)

        add_future_pickups(str(event_id))

    #logger.info(
    #  'Created reminder job for Blocks %s. Emails fire at %s, calls fire at %s',
    #  str(blocks), job['email']['fire_dt'].isoformat(),
    #  job['voice']['fire_dt'].isoformat())

    return True

#-------------------------------------------------------------------------------
def add_notification(event_id, event_dt, trig_id, _type, account, schema):
    '''Adds an event reminder for given job
    @schema: pickup_reminder notification_event schema
    @_type: one of ['phone', 'email']
    Returns:
      -True on success, False otherwise'''

    sms_enabled = False

    npu = etap.get_udf('Next Pickup Date', account).split('/')
    npu = "%s/%s/%s T08:00:00" % (npu[1],npu[0],npu[2])
    npu_dt = utils.naive_to_local(parse(npu))

    udf = {
        "status": etap.get_udf('Status', account),
        "office_notes": etap.get_udf('Office Notes', account),
        "block": etap.get_udf('Block', account),
        "pickup_dt": npu_dt,
        "future_pickup_dt": None,
        "opted_out": False,
        "cancel_pickup_url": \
            "%s/reminders/%s/%s/cancel_pickup" %
            (app.config['PUB_URL'], str(event_id),account['id'])
    }

    if _type == 'phone':
        if not etap.get_primary_phone(account):
            return False

        notifications.add(
            event_id, event_dt, trig_id, 'voice',
            etap.get_primary_phone(account), account, udf,
            content={
              'source':'template',
              'template': schema['voice']
            })
    elif _type == 'email':
        if not account.get('email'):
            return False

        notifications.add(
            event_id, event_dt, trig_id, 'email',
            account.get('email'), account, udf,
            content={
                'source': 'template',
                'template': schema['email']
            })

    return True

#-------------------------------------------------------------------------------
#@celery_app.task
def add_future_pickups(event_id):
    '''Update all reminders for given job with their future pickup dates to
    relay to opt-outs
    @event_id: str of ObjectID
    '''

    event_id = ObjectId(event_id)

    logger.info('Getting next pickups for notification vent ID \'%s\'', str(event_id))

    event = db['notification_events'].find_one({'_id':event_id})
    agency_conf = db['agencies'].find_one({'name':event['agency']})

    start = event['event_dt'] + timedelta(days=1)
    end = start + timedelta(days=90)
    cal_events = []

    try:
        for key in agency_conf['cal_ids']:
            cal_events += scheduler.get_cal_events(
                    agency_conf['cal_ids'][key],
                    start,
                    end,
                    agency_conf['google']['oauth'])

        logger.debug('%i calendar events pulled', len(cal_events))

        block_dates = {}

        # Search calendar events to find pickup date
        for cal_event in cal_events:
            block = cal_event['summary'].split(' ')[0]

            if block not in block_dates:
                dt = parse(cal_event['start']['date'] + " T08:00:00")
                block_dates[block] = utils.naive_to_local(dt)

        notific_list = db['notifications'].find({'event_id':event_id})

        # Update future pickups for every notification under this event
        for notific in notific_list:
            npu = get_next_pickup(
              notific['account']['udf']['block'],
              notific['account']['udf']['office_notes'],
              block_dates
            )

            if npu:
                db['notifications'].update_one(notific, {
                    '$set':{'account.udf.future_pickup_dt':npu}
                })
    except Exception as e:
        logger.error('add_future_pickups: %s', str(e))
        return str(e)

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

    dates.sort()

    logger.info("next_pickup for %s: %s", blocks, dates[0].strftime('%b %d %Y'))

    return dates[0]


#-------------------------------------------------------------------------------
#@celery_app.task
def _cancel(event_id, account_id):
    '''Update users eTapestry account with next pickup date and send user
    confirmation email
    @reminder_id: string form of ObjectId
    Returns: True if no errors, False otherwise
    '''
    event_id = ObjectId(event_id)
    account_id = int(account_id)

    logger.info('Cancelling pickup for \'%s\'', account_id)

    notific_list = db['notifications'].find({
        'account.id': account_id,
        'event_id': event_id
    })

    email_notification = None

    # Outdated/in-progress or deleted job?
    if notific_list == None:
        logger.error(
            'Account %s opt-out request failed. '\
            'Couldnt find notification for event_id %s',
            account_id, str(event_id))
        return False

    notific_list = list(notific_list)

    for notification in notific_list:
        if notification['type'] == 'email':
            email_notification = notification

        # Already cancelled?
        if notification['account']['udf']['opted_out'] == True:
            logger.info(
                'Account %s already opted-out. Ignoring request.',
                account_id)
            return False

        db['notifications'].update_one(notification, {
            '$set': {
                'status': 'cancelled',
                'account.udf.opted_out': True
            }})

        if not notification['account']['udf'].get('future_pickup_dt'):
            logger.error(
                'Account %s missing future pickup date (event_id %s)',
                str(event_id))
        else:
            future_pickup_dt = notification['account']['udf'].get('future_pickup_dt')

    event = db['notification_events'].find_one({'_id':event_id})

    msg = 'No Pickup ' + utils.utc_to_local(event['event_dt']).strftime('%A, %B %d')

    agency_conf = db['agencies'].find_one({'name':event['agency']})

    try:
        # Write to eTapestry
        etap.call('no_pickup', agency_conf['etapestry'], data={
            "account": account_id,
            "date": event['event_dt'].strftime('%d/%m/%Y'),
            "next_pickup": utils.utc_to_local(future_pickup_dt).strftime('%d/%m/%Y')
        })
    except Exception as e:
        logger.error("Error writing to eTap: %s", str(e))

    notifications.send_email(email_notification, agency_conf['mailgun'], key='no_pickup')

    return True

#-------------------------------------------------------------------------------
#@celery_app.task
def set_no_pickup(url, params):
    r = requests.get(url, params=params)

    if r.status_code != 200:
        logger.error('etap script "%s" failed. status_code:%i', url, r.status_code)
        return r.status_code

    logger.info('No pickup for account %s', params['account'])

    return r.status_code
