'''app.main.donors'''
import json, logging, math
from datetime import date, timedelta
from dateutil.parser import parse
from flask import g, request
from app import get_keys
from app.lib import html, mailgun
from app.main.etap import EtapError, mod_acct, get_udf, call
from app.lib.dt import ddmmyyyy_to_date as to_date
from logging import getLogger
log = getLogger(__name__)


#-------------------------------------------------------------------------------
def cache_accts(accts):

    n_mod = 0
    n_upsert = 0

    for acct in accts:
        if not 'id' in acct:
            continue

        try:
            acct['accountCreatedDate'] = parse(acct['accountCreatedDate'])
            acct['accountLastModifiedDate'] = parse(acct['accountLastModifiedDate']) if acct['accountLastModifiedDate'] else None
        except Exception as e:
            log.exception('Error parsing Acct ID %s dates', acct['id'])
            continue
        else:
            rv = g.db['accts_cache'].update_one(
                {
                    'group':g.group,
                    'account.id':acct['id'],
                    'account.accountLastModifiedDate': None or {'$lte':acct['accountLastModifiedDate']}
                },
                {'$set':{'group':g.group, 'account':acct}},
                upsert=True)

            n_mod += rv.modified_count
            n_upsert += 1 if rv.upserted_id else 0

    log.debug('Modified %s cached accounts, upserted %s', n_mod, n_upsert)

#-------------------------------------------------------------------------------
def get(acct_id):
    return call('get_acct', data={'acct_id':int(acct_id)})

#-------------------------------------------------------------------------------
def get_acct_by_ref(ref):
    return call('get_acct_by_ref', data={'ref':ref})

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
                "acct_ref": acct['ref'],
                "start": start.strftime("%d/%m/%Y"),
                "end": end.strftime("%d/%m/%Y")})
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
            data={
                "acct_refs": [acct['ref']],
                "start": cutoff_date.strftime('%d/%m/%Y'),
                "end": date.today().strftime('%d/%m/%Y')
            })[0]
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

    g.group = agcy
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
