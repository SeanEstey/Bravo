'''app.schedule'''

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

from .block_parser import get_block, block_to_rmv
from . import gcal, gsheets, etap
from . import db

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def get_next_block_date(cal_id, block, oauth):
    try:
        service = gcal.gauth(oauth)
        events = gcal.get_events(
            service,
            cal_id,
            datetime.combine(date.today(), time()),
            datetime.combine(date.today() + timedelta(weeks=10), time())
        )
    except Exception as e:
        logger.error('Could not access Res calendar: %s', str(e))
        return False

    for item in events:
        if get_block(item['summary']) == block:
            parts = item['start']['date'].split('-')
            return date(int(parts[0]), int(parts[1]), int(parts[2]))

    return False

#-------------------------------------------------------------------------------
def get_blocks(cal_id, start_date, end_date, oauth):
    '''Return list of Block names between scheduled dates'''

    blocks = []

    try:
        service = gcal.gauth(oauth)
        events = gcal.get_events(service, cal_id, start_date, end_date)
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
