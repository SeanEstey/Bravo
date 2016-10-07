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

from app import gsheets
from app import etap
from app.block_parser import get_block, block_to_rmv

from app import app, db

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def get_cal_events(cal_id, start, end, oauth):
    '''Get a list of Google Calendar events between given dates.
    @oauth: dict oauth keys for google service account authentication
    @start, @end: naive datetime objects
    Returns: list of Event items on success, False on error
    Full-day events have datetime.date objects for start date
    Event object definition: https://developers.google.com/google-apps/calendar/v3/reference/events#resource
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

    start = start.replace(tzinfo=None)
    end = end.replace(tzinfo=None)

    try:
        events_result = service.events().list(
            calendarId = cal_id,
            timeMin = start.isoformat() +'-07:00', # MST ofset
            timeMax = end.isoformat() +'-07:00', # MST offset
            singleEvents = True,
            orderBy = 'startTime'
        ).execute()
    except Exception as e:
        logger.error('Error pulling cal events: %s', str(e))
        logger.error(start.isoformat())
        return False

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
        if get_block(item['summary']):
            blocks.append(get_block(item['summary']))

    if len(blocks) > 0:
        logger.info('%d scheduled Blocks: %s', len(blocks), blocks)

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

    logger.info('Non-participant cutoff date is %s', np_cutoff.strftime('%b %d %Y'))

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
def analyze_non_participants():
    '''Create RFU's for all non-participants on scheduled dates'''

    agencies = db['agencies'].find()

    for agency in agencies:
        try:
            logger.info('%s: Analyzing non-participants in 5 days...', agency['name'])

            accounts = get_accounts(
                agency['etapestry'],
                agency['cal_ids']['res'],
                agency['google']['oauth'],
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
            logger.error('non-participation exception: %s', str(e))
            continue


