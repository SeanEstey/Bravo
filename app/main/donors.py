'''app.main.donors'''
import json, logging
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
