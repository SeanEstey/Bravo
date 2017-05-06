'''app.main.cal'''
import logging
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
from .parser import get_block, block_to_rmv
from app.lib import gcal
from . import etap
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def get_next_block_date(cal_id, block, oauth):
    service = gcal.gauth(oauth)

    if not service:
        return False

    events = gcal.get_events(
        service,
        cal_id,
        datetime.combine(date.today(), time()),
        datetime.combine(date.today() + timedelta(weeks=10), time())
    )

    for item in events:
        if get_block(item['summary']) == block:
            parts = item['start']['date'].split('-')
            return date(int(parts[0]), int(parts[1]), int(parts[2]))

    return False

#-------------------------------------------------------------------------------
def get_blocks(cal_id, start_dt, end_dt, oauth):
    '''Return list of Block names between scheduled dates
    @start, end: naive datetime objects
    '''

    blocks = []

    try:
        service = gcal.gauth(oauth)
        events = gcal.get_events(service, cal_id, start_dt, end_dt)
    except Exception as e:
        log.error('Could not access Res calendar: %s', str(e))
        return False

    for item in events:
        if get_block(item['summary']):
            blocks.append(get_block(item['summary']))

    if len(blocks) > 0:
        log.debug('%d scheduled blocks: %s', len(blocks), blocks)

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
        log.info('No Blocks found on given date')
        return []

    accounts = []

    for block in blocks:
        try:
            a = etap.call('get_query', etapestry_id,
              {'query':block, 'category':etapestry_id['query_category']})
        except Exception as e:
            log.error('Error retrieving accounts for query %s', block)

        if 'count' in a and a['count'] > 0:
            accounts = accounts + a['data']

    log.debug('found %d accounts in blocks %s', len(accounts), blocks)

    return accounts
