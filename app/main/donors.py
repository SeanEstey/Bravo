'''app.main.donors'''
import json, logging, math
from datetime import date, timedelta
from dateutil.parser import parse
from flask import g, request
from app import get_keys, get_logger
from app.lib import html, mailgun
from app.main.etap import EtapError, mod_acct, get_udf, call
from app.lib.dt import ddmmyyyy_to_date as to_date
log = get_logger('main.donors')

#-------------------------------------------------------------------------------
def get(acct_id):
    return call(
        'get_acct',
        get_keys('etapestry'),
        data={'acct_id': int(acct_id)})

#-------------------------------------------------------------------------------
def get_next_pickup(email, agcy):
    return call(
        'get_next_pickup',
        get_keys('etapestry', agcy=agcy),
        data={'email':email})

#-------------------------------------------------------------------------------
def get_donations(acct_id, start_d=None, end_d=None):
    '''Pulls all Notes and Gifts in 12 week period before @before
    Returns most recent
    @before, @after: datetime.date
    '''

    JE_NOTE = 1
    JE_GIFT = 5

    try:
        acct = get(int(acct_id))
    except Exception as e:
        log.error('couldnt find acct_id=%s', acct_id)
        return False

    '''
    # Acct was active last cycle?

    blocks = get_udf('Block', acct)
    n_blocks = float(len(blocks.split(", "))) if blocks else None

    if not n_blocks:
        log.debug(blocks)
        return False

    n_weeks_ago = math.ceil(10.0/n_blocks)
    drop_date = get_udf('Dropoff Date', acct)

    if not drop_date:
        drop_date = get_udf('Signup Date', acct)

    drop_d = to_date(drop_date)
    last_cycle_d = date.today() - timedelta(weeks=int(n_weeks_ago))

    if drop_d > last_cycle_d:
        log.debug(drop_d)
        return False

    # Search +- 1 week
    log.debug('last_cycle_d=%s', last_cycle_d)
    '''

    start = start_d if start_d else (date.today() - timedelta(weeks=12))
    end = end_d if end_d else date.today()

    log.debug('donor_history for acct_id=%s from %s to %s',
        acct['id'], start, end)

    try:
        je_list = call(
            'donor_history',
            get_keys('etapestry'),
            data={
                "acct_ref": acct['ref'],
                "start": start.strftime("%d/%m/%Y"),
                "end": end.strftime("%d/%m/%Y")})
    except Exception as e:
        log.error('donor history error for acct_id=%s. desc: %s', acct['id'], str(e))
        return False

    # Remove non-"No Pickup" notes

    gift_list = [x for x in je_list if x['type'] == JE_GIFT or (x['type'] == JE_NOTE and x['note'] == 'No Pickup')]

    # Convert "No Pickup" Notes to zero gift
    # Strip all fields except Date, Amount, Type, and Note

    for i in range(len(gift_list)):
        je = gift_list[i]

        if je['type'] == JE_NOTE and je['note'] == 'No Pickup':
            gift_list[i] = {
                'date': je['date'], #parse(je['date']),
                'type': JE_GIFT,
                'amount': 0,
                'note': 'No Pickup'
            }
        elif je['type'] == JE_GIFT:
            gift_list[i] = {
                'date': je['date'], #parse(je['date']),
                'type': JE_GIFT,
                'amount': je['amount'],
                'note': je['note']
            }

    log.debug('%s donations for acct_id=%s', len(gift_list), acct['id'])

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
        note_rv = call(func, get_keys("etapestry"), data=data)
    except Exception as e:
        raise

    if fields:
        log.debug('fields=%s', fields)
        try:
            updt_rv = call(
                'modify_acct',
                get_keys('etapestry'),
                data={
                    'acct_id':acct_id,
                    'persona': [],
                    'udf':json.loads(fields)})
        except Exception as e:
            raise

    log.debug('save_rfu result=%s', note_rv)

    return note_rv

#-------------------------------------------------------------------------------
def create_accts(accts):
    '''Called from API. g.user is set'''

    log.warning('creating %s accounts...', len(json.loads(accts)))

    try:
        rv = call('add_accts', get_keys('etapestry'), {'accts':accts})
    except Exception as e:
        log.error('add_accts. desc=%s', str(e))
        log.debug('', exc_info=True)

    log.warning('%s', rv['description'])

    if len(rv['errors']) > 0:
        log.error(rv['errors'])

#-------------------------------------------------------------------------------
def is_inactive(agcy, acct, days=270):

    drop_date = get_udf('Dropoff Date', acct)

    # Set Dropoff Date == acct creation date if empty

    if not drop_date:
        log.debug('accountCreatedDate=%s', acct['accountCreatedDate'])
        #acct_date = parse(acct['accountCreatedDate']).strftime("%d/%m/%Y")
        #signup_date = acct_date.split('/')
        #mod_acct(acct['id'], get_keys('etapestry',agcy=agcy),
        #    udf={'Dropoff Date':signup_date, 'Signup Date':signup_date})
        return

    # Must have been dropped off > @days

    delta = date.today() - to_date(drop_date)

    if delta.days < days:
        return False

    cutoff_date = date.today() - timedelta(days=days)

    # Retrieve journal entries from cutoff, see if donations made in period

    try:
        je = call(
            'get_gift_histories',
            get_keys('etapestry',agcy=agcy), {
                "acct_refs": [acct['ref']],
                "start": cutoff_date.strftime('%d/%m/%Y'),
                "end": date.today().strftime('%d/%m/%Y')})[0]
    except EtapError as e:
        log.error('get_gift_histories error for acct_id=%s. desc=%s',
            acct['id'], str(e))
        raise

    if len(je) > 0:
        return False
    else:
        log.debug('found inactive donor, acct_id="%s"', acct['id'])
        return True

#-------------------------------------------------------------------------------
def unsubscribe(agcy):
    if not request.args.get('email'):
        raise Exception('no email included in unsub')

    log.debug('unsub email=%s, agcy=%s', request.args['email'], agcy)

    conf = get_keys('mailgun',agcy=agcy)

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
        log.debug('', exc_info=True)
        return 'failed'

    return "We've received your request. "\
        "Please give us a few days to remove your email from our correspondence"
