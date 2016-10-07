import logging
import json
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId
from bson import json_util

from app import utils
from app import block_parser
from app import scheduler
from app import etap
from app.notify import events
from app.notify import notifications
from app.notify import triggers

from app import app, db

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def schedule_reminders():
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    '''

    DAYS_IN_ADVANCE_TO_SCHEDULE = 1
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

        evnt_id = events.insert(agency, block, block_date)

        for conf in agency_conf['notifications']:
            _date = block_date + timedelta(days=conf['fire_days_delta'])
            _time = time(conf['fire_hour'], conf['fire_min'])

            if conf['type'] == 'sms':
                continue
            elif conf['type'] == 'voice':
                phone_trig_id = triggers.insert(evnt_id, _date, _time, 'phone')
            elif conf['type'] == 'email':
                email_trig_id = triggers.insert(evnt_id, _date, _time, 'email')

        event_dt = utils.naive_to_local(datetime.combine(block_date,time(8,0)))

        # Add notifications
        for account in accounts:
            logger.debug(json.dumps(account))

            npu = etap.get_udf('Next Pickup Date', account).split('/')

            if len(npu) < 3:
                logger.error('Account %s missing npu. Skipping.', account['id'])
                continue

            acct_id = insert_account(account)

            insert_reminder(evnt_id, event_dt, phone_trig_id,
                            'phone', acct_id, schema)
            insert_reminder(evnt_id, event_dt, email_trig_id,
                            'email', acct_id, schema)

        add_future_pickups(str(evnt_id))

    #logger.info(
    #  'Created reminder job for Blocks %s. Emails fire at %s, calls fire at %s',
    #  str(blocks), job['email']['fire_dt'].isoformat(),
    #  job['voice']['fire_dt'].isoformat())

    return True

#-------------------------------------------------------------------------------
def insert_account(account):
    return db['accounts'].insert_one({
        'name': account['name'],
        'id': account['id'],
        'phone': etap.get_primary_phone(account),
        'email': account.get('email'),
        'udf': {
            'status': etap.get_udf('Status',account),
            'block': etap.get_udf('Block', account),
            'driver_notes': etap.get_udf('Driver Notes', account),
            'office_notes': etap.get_udf('Office Notes', account),
            'pickup_dt': etap.ddmmyyyy_to_local_dt(
                etap.get_udf('Next Pickup Date', account))
        }
    }).inserted_id

#-------------------------------------------------------------------------------
def insert_reminder(evnt_id, event_dt, trig_id, _type, acct_id, schema):
    '''Adds an event reminder for given job
    @schema: pickup_reminder notification_event schema
    @_type: one of ['phone', 'email']
    Returns:
      -True on success, False otherwise'''

    sms_enabled = False

    account = db['accounts'].find_one({'_id':acct_id})

    if _type == 'phone':
        if not account.get('phone'):
            return False

        _id =notifications.insert(
            evnt_id,
            event_dt,
            trig_id,
            acct_id,
            'voice',
            account['phone'],
            content={
              'source':'template',
              'template': schema['voice']
            })
    elif _type == 'email':
        if not account.get('email'):
            return False

        _id = notifications.insert(
            evnt_id,
            event_dt,
            trig_id,
            acct_id,
            'email',
            account.get('email'),
            content={
                'source': 'template',
                'template': schema['email']
            })

    logger.info('Inserted reminder _id %s', str(_id))
    return True

#-------------------------------------------------------------------------------
def add_future_pickups(evnt_id):
    '''Update all reminders for given job with their future pickup dates to
    relay to opt-outs
    @evnt_id: str of ObjectID
    '''

    evnt_id = ObjectId(evnt_id)

    logger.info('Getting next pickups for notification event ID \'%s\'', str(evnt_id))

    event = db['notification_events'].find_one({'_id':evnt_id})
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

        notific_list = db['notifications'].find({'evnt_id':evnt_id})

        # Update future pickups for every notification under this event
        for notific in notific_list:
            account = db['accounts'].find_one({'_id':notific['acct_id']})

            npu = get_next_pickup(
              account['udf']['block'],
              account['udf']['office_notes'],
              block_dates
            )

            if npu:
                db['accounts'].update_one({'_id':notific['acct_id']}, {
                    '$set':{'udf.future_pickup_dt':npu}
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
def _cancel(evnt_id, acct_id):
    '''Update users eTapestry account with next pickup date and send user
    confirmation email'''

    evnt_id = ObjectId(evnt_id)
    acct_id = ObjectId(acct_id)

    logger.info('Cancelling pickup for \'%s\'', acct_id)

    db['notifications'].update(
        {'acct_id': acct_id, 'evnt_id': evnt_id},
        {'$set': {'status':'cancelled', 'opted_out':True}},
        multi=True
    )
    account = db['accounts'].find_one({'_id':acct_id})
    agency_conf = db['agencies'].find_one(
        {'name': db['notification_events'].find_one({'_id':evnt_id})['agency']}
    )

    try:
        # Write to eTapestry
        etap.call(
            'no_pickup',
            agency_conf['etapestry'],
            data={
                "account": account['id'],
                "date": account['udf']['pickup_dt'].strftime('%d/%m/%Y'),
                "next_pickup": utils.tz_utc_to_local(
                    account['udf']['future_pickup_dt']).strftime('%d/%m/%Y')
            })
    except Exception as e:
        logger.error("Error writing to eTap: %s", str(e))

    notific = db['notifications'].find_one({'acct_id':acct_id,
        'evnt_id':evnt_id, 'type':'email'})

    if notific:
        notifications.send_email(notific, agency_conf['mailgun'], key='no_pickup')

    return True
