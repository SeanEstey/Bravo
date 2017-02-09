'''app.main.donors'''
import logging
from datetime import date, timedelta
from dateutil.parser import parse
from flask import g, request
from app import html, mailgun, get_keys
from app.etap import EtapError, mod_acct, get_udf, call
from app.dt import ddmmyyyy_to_date as to_date
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get(acct_id):
    return call(
        'get_acct',
        get_keys('etapestry'),
        data={'acct_id': int(acct_id)})

#-------------------------------------------------------------------------------
def create_accts(accts):
    '''Called from API. g.user is set'''

    try:
        rv = call('add_accts', get_keys('etapestry'), {'accts':accts})
    except Exception as e:
        log.error('add_accts. desc=%s', str(e))
        log.debug('', exc_info=True)

    log.info('add_accts rv=%s', rv)

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
        log.error('get_gift_histories fail. desc=%s', str(e))
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
    body = '%s has requested email unsubscription. Please contact to see if '\
            'they want to cancel the service.' % request.args['email']
    subject = 'Unsubscribe Request'

    try:
        mid = mailgun.send(conf['from'], subject, body, conf)
    except Exception as e:
        log.error(str(e))
        log.debug('', exc_info=True)
        return 'failed'

    return "We've received your request. "\
        "Please give us a few days to remove your email from our correspondence"
