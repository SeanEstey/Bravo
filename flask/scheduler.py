import json
import logging
import requests
import datetime
from dateutil.parser import parse
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
import re
from datetime import datetime,date, timedelta
from bson import Binary, Code, json_util
from bson.objectid import ObjectId
import dateutil
import re

from app import app, db, info_handler, error_handler, login_manager
from tasks import celery_app
from config import *
import gsheets
import etap

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
def get_cal_events(cal_id, start, end, oauth):
    '''Get a list of Google Calendar events between given dates.
    @oauth: dict oauth keys for google service account authentication
    Returns: list on success, False on error
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

    return service.events().list(
        calendarId = cal_id,
        timeMin = start.isoformat()+'-07:00', # MST ofset
        timeMax = end.isoformat()+'-07:00', # MST offset
        singleEvents = True,
        orderBy = 'startTime'
    ).execute()


#-------------------------------------------------------------------------------
def get_blocks(cal_id, start_date, end_date, oauth):
    '''Return list of Res Blocks between scheduled dates'''

    blocks = []

    try:
        events = get_cal_events(cal_id, start_date, end_date, oauth)
    except Exception as e:
        logger.error('Could not access Res calendar: %s', str(e))
        return False

    for item in events['items']:
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
                'get_query_accounts', {
                  'user':etapestry_id['user'],
                  'pw':etapestry_id['pw'],
                  'agency':etapestry_id['agency'],
                  'endpoint':app.config['ETAPESTRY_ENDPOINT']
                },
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
    (Dropoff Date >= 12 monthss ago and no collections in that time
    '''

    # TODO: If missing Signup Date use 'accountCreatedDate'
    # If missing Dropoff Date, use 'accountCreatedDate' + 4 weeks

    # Build list of accounts to query gift_histories for
    older_accounts = []

    for account in accounts:
        # Test if Dropoff Date was at least 12 months ago
        d = etap.get_udf('Dropoff Date', account).split('/')

        if len(d) < 3:
            continue

        dropoff_date = datetime(int(d[2]), int(d[1]), int(d[0]))
        now = datetime.now()
        delta = now - dropoff_date

        if delta.days >= 365:
            older_accounts.append(account)

    logger.info('found %s older accounts', str(len(older_accounts)))

    if len(older_accounts) == 0:
        return False

    try:
        etap_id = db['agencies'].find_one({'name':agency})['etapestry']
        keys = {'user':etap_id['user'], 'pw':etap_id['pw'],
                'agency':agency,'endpoint':app.config['ETAPESTRY_ENDPOINT']}

        gift_histories = etap.call('get_gift_histories',
          keys, {
          "account_refs": [i['ref'] for i in older_accounts],
          "start_date": str(now.day) + "/" + str(now.month) + "/" + str(now.year-1),
          "end_date": str(now.day) + "/" + str(now.month) + "/" + str(now.year)
        })
    except Exception as e:
        logger.error('Failed to get gift_histories', exc_info=True)
        return str(e)

    logger.info('found %s gift histories', str(len(gift_histories)))

    now = datetime.now()

    nps = []

    for idx, gift_history in enumerate(gift_histories):
        if len(gift_history) == 0:
            nps.append(older_accounts[idx])

    logger.info('Found %d non-participants', len(nps))

    return nps

#-------------------------------------------------------------------------------
@celery_app.task
def analyze_non_participants():
    '''Create RFU's for all non-participants on scheduled dates'''

    agencies = db['agencies'].find()

    for agency in agencies:
        logger.info('%s: Analyzing non-participants in 5 days...', agency['name'])

        accounts = get_accounts(
            agency['etapestry'],
            agency['cal_ids']['res'],
            agency['oauth'],
            days_from_now=5)

        if len(accounts) < 1:
            continue

        nps = get_nps(agency['name'], accounts)

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

        logger.info('%i calendar events pulled', len(events['items']))

        pickup_dates = {}

        for block in blocks:
            # Search calendar events to find pickup date
            for event in events['items']:
                cal_block = event['summary'].split(' ')[0]

                if cal_block == block:
                    logger.debug('Block %s Pickup Date: %s',
                        block,
                        event['start']['date']
                    )
                    dt = dateutil.parser.parse(event['start']['date'])
                    pickup_dates[block] = dt
            if block not in pickup_dates:
                logger.info('No pickup found for Block %s', block)

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

        # Only works for residential blocks with a booking block and
        # 1 natural block...fixme...
        for reminder in reminders:
            for block in reminder['custom']['block'].split(', '):
                if pickup_dates[block] > reminder['event_date']:
                    db['reminders'].update_one(
                        reminder,
                        {'$set':{'custom.next_pickup':pickup_dates[block]}})

    except Exception as e:
        logger.error('get_next_pickups', exc_info=True)
        return str(e)
