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
def get_cal_events(agency, cal_id, start, end):
    oauth = db['agencies'].find_one({'name':agency})['oauth']

    #json_key = json.load(open('oauth_credentials.json'))

    credentials = SignedJwtAssertionCredentials(
        oauth['client_email'],
        oauth['private_key'],
        ['https://www.googleapis.com/auth/calendar.readonly']
    )

    http = httplib2.Http()
    http = credentials.authorize(http)

    service = build('calendar', 'v3', http=http)

    return service.events().list(
        calendarId = cal_id,
        timeMin = start.isoformat()+'-07:00', # MST ofset
        timeMax = end.isoformat()+'-07:00', # MST offset
        singleEvents = True,
        orderBy = 'startTime'
    ).execute()


#-------------------------------------------------------------------------------
def get_blocks(agency, cal_id, start_date, end_date):
    '''Return list of Res Blocks between scheduled dates'''

    blocks = []

    try:
        events = get_cal_events(agency, cal_id, start_date, end_date)
    except Exception as e:
        logger.error('Could not access Res calendar: %s', str(e))
        return False

    for item in events['items']:
        res_block = re.match(r'^R([1-9]|10)[a-zA-Z]{1}', item['summary'])

        if res_block:
            blocks.append(res_block.group(0))

    logger.info('%d blocks found: %s', len(blocks), blocks)

    return blocks


#-------------------------------------------------------------------------------
def get_accounts(agency, days_from_now=None):
    '''Return list of eTapestry Accounts in schedule'''

    start_date = datetime.now() + timedelta(days=days_from_now)
    end_date = start_date + timedelta(hours=1)

    cal_id = db['agencies'].find_one({'name':agency})['cal_ids']['res']

    blocks = get_blocks(agency, cal_id, start_date, end_date)

    if len(blocks) < 1:
        logger.info('No Blocks found on given date')
        return False

    accounts = []

    etap = db['agencies'].find_one({'name':agency})['etapestry']
    keys = {'user':etap['user'], 'pw':etap['pw'],
            'agency':agency,'endpoint':app.config['ETAPESTRY_ENDPOINT']}

    for block in blocks:
        try:
            a = etap.call('get_query_accounts',
                keys,
                { 'query':block, 'query_category':'ETW: Routes'}
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

    try:
        etap = db['agencies'].find_one({'name':agency})['etapestry']
        keys = {'user':etap['user'], 'pw':etap['pw'],
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

    logger.info('Analyzing non-participants in 4 days...')

    agency = 'wsf' # for now

    accounts = get_accounts(agency, days_from_now=4)

    if len(accounts) < 1:
        return False

    nps = get_nps(agency, accounts)

    now = datetime.now()

    for np in nps:
        npu = etap.get_udf('Next Pickup Date', np).split('/')
        next_pickup = npu[1] + '/' + npu[0] + '/' + npu[2]

        # Update Driver/Office Notes

        gsheets.create_rfu(
          'Non-participant',
          account_number = np['id'],
          next_pickup = next_pickup,
          block = etap.get_udf('Block', np),
          date = str(now.month) + '/' + str(now.day) + '/' + str(now.year)
        )

#-------------------------------------------------------------------------------
@celery_app.task
def get_next_pickups(job_id):
    try:
        job_id = ObjectId(job_id)
        messages = db['msgs'].find({'job_id':job_id}, {'imported.block':1})
        blocks = []

        for msg in messages:
            if msg['imported']['block'] not in blocks:
                blocks.append(msg['imported']['block'])

        start = datetime.now() + timedelta(days=30)
        end = start_search + timedelta(days=70)

        events = get_cal_events(ETW_RES_CALENDAR_ID, start, end)

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

          db['msgs'].update(
            {'job_id':job_id, 'imported.block':block},
            {'$set':{'next_pickup':date}},
            multi=True
          )

    except Exception as e:
        logger.error('get_next_pickups', exc_info=True)
        return str(e)
