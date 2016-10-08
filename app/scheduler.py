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



