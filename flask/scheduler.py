import json
import logging
import requests
import datetime
from dateutil.parser import parse
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
import re
from datetime import datetime, date, time, timedelta
from bson import Binary, Code, json_util
from bson.objectid import ObjectId
import dateutil
import pytz

from config import *
from app import app, db, info_handler, error_handler, debug_handler, login_manager
from tasks import celery_app
import gsheets
import etap

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(debug_handler)
logger.setLevel(logging.DEBUG)


#-------------------------------------------------------------------------------
@celery_app.task
def setup_reminder_jobs():
    '''Setup upcoming reminder jobs for accounts for all Blocks on schedule
    '''

    agency = 'vec'
    vec = db['agencies'].find_one({'name':agency})
    settings = vec['reminders']

    accounts = []

    # Get combined Res/Bus accounts from Blocks on given date
    for cal_id in vec['cal_ids']:
        accounts += get_accounts(
          vec['etapestry'],
          vec['cal_ids'][cal_id],
          vec['oauth'],
          days_from_now=settings['days_in_advance_to_schedule'])

    if len(accounts) < 1:
        return False

    today = date.today()
    block_date = today + timedelta(days=settings['days_in_advance_to_schedule'])
    blocks = []

    for cal_id in vec['cal_ids']:
        blocks += get_blocks(
          vec['cal_ids']['res'],
          datetime.combine(block_date,time(8,0)),
          datetime.combine(block_date,time(9,0)),
          vec['oauth'])

    logger.info('Scheduling reminders for blocks %s', ', '.join(blocks))

    # Load reminder schema
    try:
        with open('templates/schemas/'+agency+'.json') as json_file:
          schemas = json.load(json_file)['reminders']
    except Exception as e:
        logger.error(str(e))

    # Create mongo 'job' and 'reminder' records

    # TODO: Fixme
    reminder_schema = schemas[0]

    local = pytz.timezone("Canada/Mountain")

    # Convert naive datetimes to local tz. Pymongo will convert to UTC when
    # inserted
    call_d = block_date + timedelta(days=settings['phone']['fire_days_delta'])
    call_t = time(settings['phone']['fire_hour'], settings['phone']['fire_min'])
    call_dt = local.localize(datetime.combine(call_d, call_t), is_dst=True)

    email_d = block_date + timedelta(days=settings['email']['fire_days_delta'])
    email_t = time(settings['email']['fire_hour'], settings['email']['fire_min'])
    email_dt = local.localize(datetime.combine(email_d, email_t), is_dst=True)

    event_dt = local.localize(datetime.combine(block_date, time(8,0)), is_dst=True)

    job = {
        'name': ', '.join(blocks),
        'agency': 'vec',
        'schema': reminder_schema,
        'event_dt': event_dt,
        'voice': {
            'fire_at': call_dt
        },
        'email': {
            'fire_at': email_dt
        },
        'status': 'pending'
    }

    job_id = db['jobs'].insert(job)
    count = 0

    for account in accounts:
        if account['phones'] != None:
            to = account['phones'][0]['number']
        else:
            to = ''

        npu = etap.get_udf('Next Pickup Date', account).split('/')

        if len(npu) < 3:
            logger.error('Account %s missing npu. Skipping.', account['id'])

            # Use the event_date as next pickup
            pickup_dt = event_dt
        else:
            npu = npu[1] + '/' + npu[0] + '/' + npu[2]
            pickup_dt = local.localize(parse(npu + " T08:00:00"), is_dst=True)

        db['reminders'].insert({
          "job_id": job['_id'],
          "agency": job['agency'],
          "name": account['name'],
          "account_id": account['id'],
          "event_dt": pickup_dt, # the current pickup date
          "voice": {
            "status": "pending",
            "to": to, # TODO: Fixme
            "attempts": 0,
          },
          "email": {
            "recipient": account['email'],
            "status": "pending"
          },
          "custom": {
            "status": etap.get_udf('Status', account),
            "office_notes": etap.get_udf('Office Notes', account),
            "block": etap.get_udf('Block', account)
          }
        })

        count+=1

    db['jobs'].update_one(job, {'$set':{'voice.count':count}})

    # Update their pickup dates
    add_future_pickups(str(job_id))

    logger.info(
      'Created reminder job for Blocks %s. Emails fire at %s, calls fire at %s',
      str(blocks), job['email']['fire_at'].isoformat(),
      job['voice']['fire_at'].isoformat())

    return True


#-------------------------------------------------------------------------------
def get_cal_events(cal_id, start, end, oauth):
    '''Get a list of Google Calendar events between given dates.
    @oauth: dict oauth keys for google service account authentication
    @start, @end: naive datetime objects
    Returns: list on success, False on error
    Full-day events have datetime.date objects for start date
    Event object definition: lhttps://developers.google.com/google-apps/calendar/v3/reference/events#resource
    '''

    try:
        credentials = SignedJwtAssertionCredentials(
            oauth['client_email'],
            oauth['private_key'],
            ['https://www.googleapis.com/auth/calendar.readonly']
        )

        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build('calendar', 'v3', http=http)
    except Exception as e:
        logger.error('Error authorizing Google Calendar ID \'%s\'\n%s', cal_id,str(e))
        return False

    events_result = service.events().list(
        calendarId = cal_id,
        timeMin = start.isoformat()+'-07:00', # MST ofset
        timeMax = end.isoformat()+'-07:00', # MST offset
        singleEvents = True,
        orderBy = 'startTime'
    ).execute()

    events = events_result.get('items', [])

    return events


#-------------------------------------------------------------------------------
def get_blocks(cal_id, start_date, end_date, oauth):
    '''Return list of Block names between scheduled dates'''

    blocks = []

    try:
        events = get_cal_events(cal_id, start_date, end_date, oauth)
    except Exception as e:
        logger.error('Could not access Res calendar: %s', str(e))
        return False

    for item in events:
        # TODO: Only matches Residential blocks on 10 week cycle
        res_block = re.match(r'^R([1-9]|10)[a-zA-Z]{1}', item['summary'])

        if res_block:
            blocks.append(res_block.group(0))

    logger.info('%d blocks found: %s', len(blocks), blocks)

    return blocks

#-------------------------------------------------------------------------------
def get_accounts(etapestry_id, cal_id, oauth, days_from_now=None):
    '''Return list of eTapestry Accounts from all scheduled routes in given
    calendar on the date specified.
    '''

    start_date = datetime.now() + timedelta(days=days_from_now)
    end_date = start_date + timedelta(hours=1)

    blocks = get_blocks(cal_id, start_date, end_date, oauth)

    if len(blocks) < 1:
        logger.info('No Blocks found on given date')
        return []

    accounts = []

    for block in blocks:
        try:
            a = etap.call(
              'get_query_accounts',
              etapestry_id,
              {'query':block, 'query_category':etapestry_id['query_category']}
            )
        except Exception as e:
            logger.error('Error retrieving accounts for query %s', block)

        if 'count' in a and a['count'] > 0:
            accounts = accounts + a['data']

    logger.info('Found %d accounts in blocks %s', len(accounts), blocks)

    return accounts

#-------------------------------------------------------------------------------
def get_nps(agency, accounts):
    '''Analyze list of eTap account objects for non-participants
    which is an active account with no > $0 gifts in past X days where X is
    set by db['agency']['config']['non-participant days']
    Output: list of np's, empty list if none found
    '''

    # Build list of accounts to query gift_histories for
    viable_accounts = []

    agency_settings = db['agencies'].find_one({'name':agency})

    etap_id = agency_settings['etapestry']

    keys = {'user':etap_id['user'], 'pw':etap_id['pw'],
            'agency':agency,'endpoint':app.config['ETAPESTRY_ENDPOINT']}

    for account in accounts:
        # Test if Dropoff Date was at least 12 months ago
        d = etap.get_udf('Dropoff Date', account).split('/')

        if len(d) < 3:
            date_str = parse(account['accountCreatedDate']).strftime("%d/%m/%Y")

            d = date_str.split('/')

            # If missing Signup Date or Dropoff Date, use 'accountCreatedDate'
            try:
                etap.call('modify_account', keys, {
                  'id': account['id'],
                  'udf': {
                    'Dropoff Date': date_str,
                    'Signup Date': date_str
                  },
                  'persona': []
                })
            except Exception as e:
                logger.error('Error modifying account %s: %s', account['id'], str(e))
                continue

        dropoff_date = datetime(int(d[2]), int(d[1]), int(d[0]))
        now = datetime.now()
        time_active = now - dropoff_date

        # Account must have been active for >= non_participant_days
        if time_active.days >= agency_settings['config']['non_participant_days']:
            viable_accounts.append(account)

    logger.info('found %s older accounts', str(len(viable_accounts)))

    if len(viable_accounts) == 0:
        return []

    np_cutoff = now - timedelta(days=agency_settings['config']['non_participant_days'])

    logger.info('Non-participant cutoff date is %', np_cutoff.strftime('%b %d %Y'))

    try:
        # Retrieve non-zero gift donations from non-participant cutoff date to
        # present
        gift_histories = etap.call('get_gift_histories', keys, {
          "account_refs": [i['ref'] for i in viable_accounts],
          "start_date": str(np_cutoff.day) + "/" + str(np_cutoff.month) + "/" +str(np_cutoff.year),
          "end_date": str(now.day) + "/" + str(now.month) + "/" + str(now.year)
        })
    except Exception as e:
        logger.error('Failed to get gift_histories', exc_info=True)
        return str(e)

    now = datetime.now()

    nps = []

    for idx, gift_history in enumerate(gift_histories):
        if len(gift_history) == 0:
            nps.append(viable_accounts[idx])

    logger.info('Found %d non-participants', len(nps))

    return nps

#-------------------------------------------------------------------------------
@celery_app.task
def analyze_non_participants():
    '''Create RFU's for all non-participants on scheduled dates'''

    agencies = db['agencies'].find()

    for agency in agencies:
        try:
            logger.info('%s: Analyzing non-participants in 5 days...', agency['name'])

            accounts = get_accounts(
                agency['etapestry'],
                agency['cal_ids']['res'],
                agency['oauth'],
                days_from_now=5)

            if len(accounts) < 1:
                continue

            nps = get_nps(agency['name'], accounts)

            if len(nps) < 1:
                continue

            now = datetime.now()

            for np in nps:
                npu = etap.get_udf('Next Pickup Date', np).split('/')

                if len(npu) < 3:
                    next_pickup = False
                else:
                    next_pickup = npu[1] + '/' + npu[0] + '/' + npu[2]

                # Update Driver/Office Notes

                gsheets.create_rfu(
                  agency['name'],
                  'Non-participant',
                  account_number = np['id'],
                  next_pickup = next_pickup,
                  block = etap.get_udf('Block', np),
                  date = str(now.month) + '/' + str(now.day) + '/' + str(now.year)
                )
        except Exception as e:
            logger.error('non-participation exception: %s' + str(e))
            continue

#-------------------------------------------------------------------------------
def get_next_pickup(blocks, office_notes, block_dates):
    '''Given list of blocks, find next scheduled date
    @blocks: string of comma-separated block names
    '''

    block_list = blocks.split(', ')

    # Remove temporary blocks
    if office_notes:
        rmv = re.search(r'(\*{3}RMV\s(B|R)\d{1,2}[a-zA-Z]{1}\*{3})', office_notes)

        if rmv:
            block_list.remove(re.search(r'(B|R\d{1,2}[a-zA-Z]{1})', rmv.group(0)).group(0))
            logger.info("Removed temp block %s from %s", str(rmv.group(0)), str(block_list))

    # Find all matching dates and sort chronologically to find solution
    dates = []

    for block in block_list:
        if block in block_dates:
            dates.append(block_dates[block])

    dates.sort()

    logger.info("next_pickup for %s: %s", blocks, dates[0].strftime('%b %d %Y'))

    return dates[0]


#-------------------------------------------------------------------------------
@celery_app.task
def add_future_pickups(job_id):
    '''Update all reminders for given job with their future pickup dates to
    relay to opt-outs
    @job_id: str of ObjectID
    '''

    logger.info('Getting next pickups for Job ID \'%s\'', job_id)

    job = db['jobs'].find_one({'_id':ObjectId(job_id)})
    agency = db['agencies'].find_one({'name':job['agency']})

    start = datetime.now() + timedelta(days=3)
    end = start + timedelta(days=90)
    events = []

    try:
        for cal_id in agency['cal_ids']:
            events += get_cal_events(agency['cal_ids'][cal_id], start, end, agency['oauth'])

        logger.info('%i calendar events pulled', len(events))

        block_dates = {}
        local = pytz.timezone("Canada/Mountain")

        # Search calendar events to find pickup date
        for event in events:
            block = event['summary'].split(' ')[0]

            if block not in block_dates:
                dt = dateutil.parser.parse(event['start']['date'] + " T08:00:00")
                local_dt = local.localize(dt,is_dst=True)
                block_dates[block] = local_dt

        reminders = db['reminders'].find({'job_id':ObjectId(job_id)})

        for reminder in reminders:
            npu = get_next_pickup(
              reminder['custom']['block'],
              reminder['custom']['office_notes'],
              block_dates)

            if npu:
                db['reminders'].update_one(
                  reminder,
                  {'$set':{'custom.future_pickup_dt':npu}}
                )
    except Exception as e:
        logger.error('add_future_pickups: %s', str(e))
        return str(e)

        '''
        logger.debug(json.dumps(pickup_dates, default=json_util.default))

        # Now we should have pickup dates for all blocks on job
        # Iterate through each msg and store pickup_date
        for block, date in pickup_dates.iteritems():
          logger.debug('Updating all %s with Next Pickup: %s', block, date)

          db['reminders'].update(
            {'job_id':ObjectId(job_id), 'custom.block':block},
            {'$set':{'custom.future_pickup_dt':date}},
            multi=True
          )

        # Finish all reminders still missing pickup dates (i.e. have multiple
        # blocks)
        reminders = db['reminders'].find(
            {'job_id':ObjectId(job_id),
             'custom.future_pickup_dt': {'$exists': False}})

        logger.info('%s missing next_pickups to update', str(reminders.count()))

        local = pytz.timezone("Canada/Mountain")

        # Only works for residential blocks with a booking block and
        # 1 natural block...fixme...
        for reminder in reminders:
            event_dt = reminder['event_dt'].replace(tzinfo=pytz.utc).astimezone(local)

            for block in reminder['custom']['block'].split(', '):
                if pickup_dates[block] > event_dt:
                    db['reminders'].update_one(
                        reminder,
                        {'$set':{'custom.future_pickup_dt':pickup_dates[block]}})
        '''
