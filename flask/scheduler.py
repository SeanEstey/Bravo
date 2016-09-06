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
import re
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

    accounts = get_accounts(
        vec['etapestry'],
        vec['cal_ids']['res'],
        vec['oauth'],
        days_from_now=settings['days_in_advance_to_schedule'])

    if len(accounts) < 1:
        return False

    today = date.today()
    block_date = today + timedelta(days=settings['days_in_advance_to_schedule'])

    blocks = get_blocks(
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

    event_date = local.localize(datetime.combine(block_date, time(8,0)), is_dst=True)

    job = {
        'name': ', '.join(blocks),
        'agency': 'vec',
        'schema': reminder_schema,
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
            continue

        npu = npu[1] + '/' + npu[0] + '/' + npu[2]
        pickup_date = local.localize(parse(npu + " T08:00:00"), is_dst=True)

        db['reminders'].insert({
          "job_id": job['_id'],
          "agency": job['agency'],
          "name": account['name'],
          "account_id": account['id'],
          "event_date": pickup_date, # the current pickup date
          "voice": {
            "status": "pending",
            "to": to, # TODO: Fixme
            "attempts": 0,
          },
          "email": {
            "recipient": account['email'],  # TODO: fixme
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
    get_next_pickups(str(job_id))

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
@celery_app.task
def get_next_pickups(job_id):
    '''Update all reminders for given job with their future pickup dates to
    relay to opt-outs
    @job_id: str of ObjectID
    '''

    logger.info('Getting next pickups for Job ID \'%s\'', job_id)

    reminders = db['reminders'].find({'job_id':ObjectId(job_id)}, {'custom.block':1})
    blocks = []

    for reminder in reminders:
        for block in reminder['custom']['block'].split(', '):
            if block not in blocks:
                blocks.append(block)

    #if reminder['custom']['block'] not in blocks:
    #    blocks.append(reminder['custom']['block'])

    start = datetime.now() + timedelta(days=30)
    end = start + timedelta(days=70)

    job = db['jobs'].find_one({'_id':ObjectId(job_id)})
    agency = db['agencies'].find_one({'name':job['agency']})

    try:
        events = get_cal_events(agency['cal_ids']['res'], start, end, agency['oauth'])

        logger.info('%i calendar events pulled', len(events))

        pickup_dates = {}

        for block in blocks:
            # Search calendar events to find pickup date
            for event in events:
                cal_block = event['summary'].split(' ')[0]

                if cal_block == block:
                    logger.debug('Block %s Pickup Date: %s',
                        block,
                        event['start']['date']
                    )

                    dt = dateutil.parser.parse(event['start']['date'] + " T08:00:00")
                    local = pytz.timezone("Canada/Mountain")
                    local_dt = local.localize(dt,is_dst=True)

                    pickup_dates[block] = local_dt
            if block not in pickup_dates:
                logger.info('No pickup found for Block %s', block)

        logger.debug(json.dumps(pickup_dates, default=json_util.default))

        # Now we should have pickup dates for all blocks on job
        # Iterate through each msg and store pickup_date
        for block, date in pickup_dates.iteritems():
          logger.debug('Updating all %s with Next Pickup: %s', block, date)

          db['reminders'].update(
            {'job_id':ObjectId(job_id), 'custom.block':block},
            {'$set':{'custom.next_pickup':date}},
            multi=True
          )

        # Finish all reminders still missing pickup dates (i.e. have multiple
        # blocks)
        reminders = db['reminders'].find(
            {'job_id':ObjectId(job_id),
             'custom.next_pickup': {'$exists': False}})

        logger.info('%s missing next_pickups to update', str(reminders.count()))

        # Only works for residential blocks with a booking block and
        # 1 natural block...fixme...
        for reminder in reminders:
            event_date = reminder['event_date'].replace(tzinfo=pytz.utc).astimezone(local)

            for block in reminder['custom']['block'].split(', '):
                if pickup_dates[block] > event_date:
                    db['reminders'].update_one(
                        reminder,
                        {'$set':{'custom.next_pickup':pickup_dates[block]}})

    except Exception as e:
        logger.error('get_next_pickups', exc_info=True)
        return str(e)
