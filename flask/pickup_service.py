import logging
import json
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId


import utils
import scheduler
import etap
import notifications
from app import app, db, info_handler, error_handler, debug_handler

logger = logging.getLogger(__name__)
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
@celery_app.task
def schedule_reminder_events():
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    '''

    DAYS_IN_ADVANCE_TO_SCHEDULE = 2
    agency = 'vec'

    agency_conf = db['agencies'].find_one({'name':agency})

    blocks = []
    block_date = date.today() + timedelta(days=DAYS_IN_ADVANCE_TO_SCHEDULE)

    for key in agency_conf['cal_ids']:
        blocks += get_blocks(
            agency_conf['cal_ids'][key],
            datetime.combine(block_date,time(8,0)),
            datetime.combine(block_date,time(9,0)),
            agency_conf['google']['oauth']
        )

    try:
        with open('templates/schemas/'+agency+'.json') as json_file:
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
                })
        except Exception as e:
            logger.error('Error retrieving accounts for query %s', block)

        if len(accounts) < 1:
            continue

        # Create notification event and add triggers

        event_id = notifications.add_event(agency, block, block_date)

        for conf in agency_conf['notifications']:
            _date = block_date + timedelta(days=conf['fire_days_delta'])
            _time = time(conf['fire_hour'], conf['fire_min'])

            if conf['type'] == 'sms':
                continue
            elif conf['type'] == 'voice':
                phone_trig_id = notifications.add_trigger(
                    event_id, _date, _time, 'phone')
            elif conf['type'] == 'email':
                email_trig_id = notifications.add_trigger(
                    event_id, _date, _time, 'email')

        # Add notifications
        for account in accounts:
            npu = etap.get_udf('Next Pickup Date', account).split('/')

            if len(npu) < 3:
                logger.error('Account %s missing npu. Skipping.', account['id'])

                # Use the event_date as next pickup
                pickup_dt = event_dt
            else:
                npu = "%s/%s/%s T08:00:00" % (npu[1],npu[0],npu[2])
                pickup_dt = utils.localize(parse(npu))

            add_notification(event_id, phone_trig_id, 'phone', account, schema)
            add_notification(event_id, email_trig_id, 'email', account, schema)

        add_future_pickups(str(event_id))

    #logger.info(
    #  'Created reminder job for Blocks %s. Emails fire at %s, calls fire at %s',
    #  str(blocks), job['email']['fire_dt'].isoformat(),
    #  job['voice']['fire_dt'].isoformat())

    return True

#-------------------------------------------------------------------------------
def add_notification(event_id, trig_id, _type, account, reminder_schema):
    '''Adds an event reminder for given job
    @schema: pickup_reminder notification_event schema
    Can contain 1-3 reminder objects: 'sms', 'voice', 'email'
    Returns:
      -True on success, False otherwise'''

    sms_enabled = False

    udf = {
        "status": etap.get_udf('Status', account),
        "office_notes": etap.get_udf('Office Notes', account),
        "block": etap.get_udf('Block', account),
        "future_pickup_dt": None
    }

    if _type == 'phone':
        if not etap.get_phone(account):
            return False

        notifications.add(
            event_id, trig_id, 'voice',
            etap.get_primary_phone(account), account, udf,
            content={
              'source':'template',
              'template':reminder_schema['voice']
            })
    elif _type == 'email':
        if not account.get('email'):
            return False

        notifications.add(
            event_id, trig_id, 'email',
            account.get('email'), account, udf,
            content={
                'source': 'template',
                'template': reminder_schema['email']
            })

    return True

#-------------------------------------------------------------------------------
@celery_app.task
def add_future_pickups(event_id):
    '''Update all reminders for given job with their future pickup dates to
    relay to opt-outs
    @event_id: str of ObjectID
    '''

    event_id = ObjectId(event_id)

    logger.info('Getting next pickups for Job ID \'%s\'', str(event_id))

    notification_event = db['notification_events'].find_one({'_id':event_id})
    agency = db['agencies'].find_one({'name':notification_event['agency']})

    start = notification_event['event_dt'] + timedelta(days=1)
    end = start + timedelta(days=90)
    events = []

    try:
        for cal_id in agency['cal_ids']:
            events += scheduler.get_cal_events(
                    agency['cal_ids'][cal_id],
                    start,
                    end,
                    agency['google']['oauth'])

        logger.debug('%i calendar events pulled', len(events))

        block_dates = {}

        # Search calendar events to find pickup date
        for event in events:
            block = event['summary'].split(' ')[0]

            if block not in block_dates:
                dt = parse(event['start']['date'] + " T08:00:00")
                block_dates[block] = utils.localize(dt)

        notifications = db['notifications'].find({'event_id':event_id})

        for notification in notifications:
            npu = get_next_pickup(
              notification['account']['udf']['block'],
              notification['account']['udf']['office_notes'],
              block_dates)

            if npu:
                db['notifications'].update_one(
                  notification,
                  {'$set':{'account.udf.future_pickup_dt':npu}}
                )
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
        rmv = block_to_rmv(office_notes)

        if rmv:
            block_list.remove(rmv)
            logger.info("Removed temp block %s from %s", rmv, str(block_list))

    # Find all matching dates and sort chronologically to find solution
    dates = []

    for block in block_list:
        if block in block_dates:
            dates.append(block_dates[block])

    dates.sort()

    #logger.info("next_pickup for %s: %s", blocks, dates[0].strftime('%b %d %Y'))

    return dates[0]
