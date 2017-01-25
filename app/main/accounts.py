'''app.main.accounts'''
import logging
from datetime import date, timedelta
from dateutil.parser import parse
from flask import g
from .. import get_keys, etap
from ..etap import EtapError, mod_acct, get_udf, ddmmyyyy_to_date as to_date
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get(acct_id):
    return etap.call(
        'get_account',
        get_keys('etapestry'),
        data={'account_number': int(acct_id)})

#-------------------------------------------------------------------------------
def is_inactive_donor(agcy, acct, days=270):

    drop_date = get_udf('Dropoff Date', acct)

    # Set Dropoff Date == acct creation date if empty

    if not drop_date:
        acct_date = parse(acct['accountCreatedDate']).strftime("%d/%m/%Y")
        signup_date = acct_date.split('/')

        mod_acct(acct['id'], get_keys('etapestry',agcy=agcy),
            udf={'Dropoff Date':signup_date, 'Signup Date':signup_date})

    # Must have been dropped off > @days

    delta = date.today() - to_date(drop_date)

    if delta.days < days:
        return False

    cutoff_date = date.today() - timedelta(days=days)

    log.info('Cutoff date=%s', cutoff_date.strftime('%b %d %Y'))

    # Retrieve journal entries from cutoff, see if donations made in period

    try:
        je = etap.call(
            'get_gift_histories',
            get_keys('etapestry',agcy=agcy), {
                "account_refs": [acct['ref']],
                "start_date": cutoff_date.strftime('%d/%b/%Y'),
                "end_date": date.today().strftime('%d/%b/%Y')})[0]
    except EtapError as e:
        log.error('get_gift_histories fail. desc=%s', str(e))
        raise

    log.debug(je)

    if len(je) > 0:
        log.debug('acct_id=%s is active', acct['id'])
        return False
    else:
        log.info('acct_id=%s is inactive', acct['id'])
        return True
