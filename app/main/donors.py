'''app.main.donors'''
import json, logging, math
from datetime import date, timedelta, datetime
from dateutil.parser import parse
from flask import g, request
from app import get_keys
from app.lib import html, mailgun
from app.main.etapestry import EtapError, mod_acct, get_acct, get_udf, call
from app.lib.dt import ddmmyyyy_to_date as to_date
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def get(aid, ref=None, sync_ytd_gifts=False):

    if sync_ytd_gifts and ref:
        from app.main.tasks import _get_gifts
        now = date.today()
        rv = _get_gifts.delay(ref, date(now.year,1,1), date(now.year,12,31))

    return get_acct(aid)

#-------------------------------------------------------------------------------
def ytd_gifts(ref, year):

    jan_1 = datetime(year,1,1)
    dec_31 = datetime(year,12,31)

    gifts = g.db['cachedGifts'].find({
        'group':g.group,
        'gift.accountRef':ref,
        'gift.date': {'$gte':jan_1, '$lte':dec_31}
    })

    log.debug('Retrieved %s cached Gifts', gifts.count())
    return list(gifts)

#-------------------------------------------------------------------------------
def get_next_pickup(email):
    return call('get_next_pickup', data={'email':email})

#-------------------------------------------------------------------------------
def get_donations(acct_id, start_d=None, end_d=None):
    '''Pulls all Notes and Gifts in given period
    @before, @after: datetime.date
    '''

    JE_NOTE = 1
    JE_GIFT = 5

    try:
        acct = get(int(acct_id))
    except Exception as e:
        log.exception('couldnt find acct_id=%s', acct_id)
        raise

    start = start_d if start_d else (date.today() - timedelta(weeks=12))
    end = end_d if end_d else date.today()

    try:
        je_list = call(
            'donor_history',
            data={
                "ref": acct['ref'],
                "startDate": start.strftime("%d/%m/%Y"),
                "endDate": end.strftime("%d/%m/%Y")},
            cache=True)
    except Exception as e:
        log.exception('Failed to get donations for Acct #%s.', acct['id'],
            extra={'exception':str(e)})
        raise

    # Remove non-"No Pickup" notes

    gift_list = [x for x in je_list if x['type'] == JE_GIFT or (x['type'] == JE_NOTE and x['note'] == 'No Pickup')]

    # Convert "No Pickup" Notes to zero gift
    # Strip all fields except Date, Amount, Type, and Note

    for i in range(len(gift_list)):
        je = gift_list[i]

        if je['type'] == JE_NOTE and je['note'] == 'No Pickup':
            gift_list[i] = {
                'id': acct['id'],
                'date': je['date'],
                'amount': 0.0,
                'note': 'No Pickup'
            }
        elif je['type'] == JE_GIFT:
            gift_list[i] = {
                'id': acct['id'],
                'date': je['date'],
                'amount': float(je['amount'])
            }

    return gift_list

#-------------------------------------------------------------------------------
def save_rfu(acct_id, body, date=False, ref=False, fields=False):
    '''Add or update RFU Journal Note for acct, update any necessary User
    Defined Fields
    '''

    func = 'update_note' if ref else 'add_note'
    data = {
        "ref": ref,
        "acct_id": acct_id,
        "body": body,
        "date": date}

    try:
        note_rv = call(func, data=data)
    except Exception as e:
        raise

    if fields:
        try:
            updt_rv = call(
                'modify_acct',
                data={
                    'acct_id':acct_id,
                    'persona': [],
                    'udf':json.loads(fields)})
        except Exception as e:
            raise

    log.debug('Created issue in Bravo Sheets', extra={'fields':note_rv})

    return note_rv

#-------------------------------------------------------------------------------
def create_accts(accts):
    '''Called from API. g.user is set'''

    log.warning('Creating %s accounts...', len(json.loads(accts)))

    try:
        rv = call('add_accts', data={'accts':accts})
    except Exception as e:
        log.error('add_accts. desc=%s', str(e))
        log.debug(str(e))

    log.warning('%s', rv['description'])

    if len(rv['errors']) > 0:
        log.error(rv['errors'])

#-------------------------------------------------------------------------------
def is_inactive(acct, days=270):

    drop_date = get_udf('Dropoff Date', acct)

    # Set Dropoff Date == acct creation date if empty

    if not drop_date:
        log.debug('accountCreatedDate=%s', acct['accountCreatedDate'])
        return

    # Must have been dropped off > @days

    delta = date.today() - to_date(drop_date)

    if delta.days < days:
        return False

    cutoff_date = date.today() - timedelta(days=days)

    # Retrieve journal entries from cutoff, see if donations made in period

    try:
        gifts = call(
            'get_gifts',
            data={
                "ref": acct['ref'],
                "startDate": cutoff_date.strftime('%d/%m/%Y'),
                "endDate": date.today().strftime('%d/%m/%Y')
            },
            cache=True
        )
    except EtapError as e:
        log.exception('Failed to retrieve gifts for Account #%s.', acct['id'])
        raise

    if len(gifts) > 0:
        return False
    else:
        log.debug('Inactive donor: Account #%s', acct['id'])
        return True

#-------------------------------------------------------------------------------
def unsubscribe(group):
    if not request.args.get('email'):
        raise Exception('no email included in unsub')

    g.group = group
    log.debug('unsub email=%s', request.args['email'])
    conf = get_keys('mailgun')

    try:
        mailgun.send(
            conf['from'],
            'Unsubscribe Request',
            '%s has requested email unsubscription. Please contact to see if '\
            'they want to cancel the service.' % request.args['email'],
            conf,
            v={'type':'unsub'})
    except Exception as e:
        log.error(str(e))
        log.debug(str(e))
        return 'failed'

    return "We've received your request. "\
        "Please give us a few days to remove your email from our correspondence"
