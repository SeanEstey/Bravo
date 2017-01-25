'''app.main.tasks'''
import logging
from datetime import date, timedelta
from flask import g
from app import cal, celery, gsheets, get_keys
from app.gsheets import gauth, append_row, get_row
from app.etap import get_udf, mod_acct, ddmmyyyy_to_mmddyyyy as swap_dd_mm
import app.main.donors
from app.main.receipts import generate
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def find_inactive_donors(self, agcy=None, in_days=5, max_inactive_days=None, **rest):
    '''Create RFU's for all non-participants on scheduled dates
    '''

    if agcy:
        agencies = [g.db.agencies.find_one({'name':agcy})]
    else:
        agencies = g.db.agencies.find({})

    for agency in agencies:
        agcy = agency['name']
        if not max_inactive_days:
            max_inactive_days = agency['config']['non_participant_days']
        log.info('%s: Analyzing non-participants in 5 days...', agcy)

        accts = cal.get_accounts(
            agency['etapestry'],
            agency['cal_ids']['res'],
            agency['google']['oauth'],
            days_from_now=in_days)

        if len(accts) < 1:
            continue

        for acct in accts:
            if not donors.is_inactive(agcy, acct, days=max_inactive_days):
                continue

            npu = get_udf('Next Pickup Date', acct)

            if len(npu.split('/')) == 3:
                npu = swap_dd_mm(npu)

            mod_acct(
                acct['id'],
                get_keys('etapestry',agcy=agcy),
                udf={
                    'Office Notes':\
                    '%s\n%s: non-participant (inactive for %s days)'%(
                    get_udf('Office Notes', acct),
                    date.today().strftime('%b%-d %Y'),
                    max_inactive_days)})

            create_rfu(
                agcy,
                'Non-participant. No collection in %s days.' % max_inactive_days,
                options={
                    'Account Number': acct['id'],
                    'Next Pickup Date': npu,
                    'Block': get_udf('Block', acct),
                    'Date': date.today().strftime('%-m/%-d/%Y'),
                    'Driver Notes': get_udf('Driver Notes', acct),
                    'Office Notes': get_udf('Office Notes', acct)})

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def send_receipts(self, entries, **rest):
    '''Email receipts to recipients and update email status on Bravo Sheets.
    Sheets->Routes worksheet.
    @entries: array of gift entry dicts->
        {'amount':float, 'date':str,'from':{'row':int,'upload_status':str(db_ref),'worksheet':str}}
    '''

    try:
        # Get all eTapestry account data.
        # List is indexed the same as @entries arg list
        accts = etap.call(
            'get_accounts',
            get_keys('etapestry'),
            {"account_numbers": [i['account_number'] for i in entries]})
    except Exception as e:
        log.error('Error retrieving accounts from etap: %s', str(e))
        return False

    gift_accts = []
    g.track = {
        'zeros': 0,
        'drop_followups': 0,
        'cancels': 0,
        'no_email': 0,
        'gifts': 0
    }
    g.ss_id = get_keys('google')['ss_id']
    g.service = gauth(get_keys('google')['oauth'])
    g.headers = get_row(g.service, g.ss_id, 'Routes', 1)

    for i in range(0, len(accts)):
        r = generate(accts[i], entries[i])

        if r == 'wait':
            gift_accts.append({
                'entry': entries[i], 'account': accts[i]})

    log.info(\
        'Receipts sent, zeros=%s, drop_followups=%s, cancels=%s, no_emails=%s',
        tracker['zeros'], tracker['drop_followups'], tracker['cancels'],
        tracker['no_email'])

    # All receipts sent except Gifts. Query Journal Histories

    if len(gift_accts) == 0:
        return

    year = parse(gift_accts[0]['entry']['date']).year
    acct_refs = [i['account']['ref'] for i in gift_accts]
    gift_histories = get_gifts_ytd(acct_refs, year)

    for i in range(0, len(gift_accts)):
        r = generate(
            gift_accts[i]['account'],
            entries[i],
            gift_history=gift_histories[i])

    log.info('Gift receipts sent=%s', len(gift_accts))

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def create_rfu(self, agcy, note, options=None, **rest):

    service = gauth(get_keys('google',agcy=agcy)['oauth'])
    ss_id = get_keys('google',agcy=agcy)['ss_id']
    wks = 'RFU'
    headers = get_row(service, ss_id, wks, 1)
    rfu = [''] * len(headers)
    rfu[headers.index('Request Note')] = note

    log.debug(headers)
    log.debug(options)

    for field in headers:
        if field in options:
            rfu[headers.index(field)] = options[field]

    append_row(service, ss_id, wks, rfu)
    log.debug('Creating RFU=%s', rfu)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_accts_sms(self, agcy=None, in_days=None, **rest):
    '''Verify that all accounts in upcoming residential routes with mobile
    numbers are set up to interact with SMS system'''

    agency_name = args[0] # FIXME
    days_delta = args[1] # FIXME

    import re
    from . import cal
    from app.main import sms

    if days_delta == None:
        days_delta = 3
    else:
        days_delta = int(days_delta)

    if agency_name:
        conf = db.agencies.find_one({'name':agency_name})

        accounts = cal.get_accounts(
            conf['etapestry'],
            conf['cal_ids']['res'],
            conf['google']['oauth'],
            days_from_now=days_delta)

        if len(accounts) < 1:
            return False

        r = sms.enable(agency_name, accounts)

        log.info('%s --- updated %s accounts for SMS. discovered %s mobile numbers ---%s',
                    bcolors.OKGREEN, r['n_sms'], r['n_mobile'], bcolors.ENDC)
    else:
        agencies = db.agencies.find({})

        for agency in agencies:
            # Get accounts scheduled on Residential routes 3 days from now
            accounts = cal.get_accounts(
                agency['etapestry'],
                agency['cal_ids']['res'],
                agency['google']['oauth'],
                days_from_now=days_delta)

            if len(accounts) < 1:
                return False

            r = sms.enable(agency['name'], accounts)

            log.info('%s --- updated %s accounts for SMS. discovered %s mobile numbers ---%s',
                        bcolors.OKGREEN, r['n_sms'], r['n_mobile'], bcolors.ENDC)



#-------------------------------------------------------------------------------
@celery.task(bind=True)
def add_gsheets_signup(self, data, **rest):
    from app.main import signups
    signup = args[0] # FIXME

    try:
        return signups.add(signup)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())
