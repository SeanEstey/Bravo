'''app.main.tasks'''
import logging
from datetime import date, timedelta
from flask import g
from app import cal, celery, gsheets, get_keys
from app.gsheets import gauth, get_row
from app.etap import get_udf, mod_acct
from app.accounts import is_inactive_donor
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def non_participants(self, *args, **kwargs):
    '''Create RFU's for all non-participants on scheduled dates
    '''

    agencies = g.db.agencies.find({})

    for agency in agencies:
        agcy = agency['name']
        log.info('%s: Analyzing non-participants in 5 days...', agcy)

        accts = cal.get_accounts(
            agency['etapestry'],
            agency['cal_ids']['res'],
            agency['google']['oauth'],
            days_from_now=5)

        if len(accts) < 1:
            continue

        max_inactive_days = agency[''] # TODO: finish me

        for acct in accts:
            if not is_inactive_donor(acct):
                continue

            npu = get_udf('Next Pickup Date', acct)

            if len(npu.split('/')) == 3:
                npu = etap.ddmmyyyy_to_mmddyyyy(npu)

            mod_acct(
                acct['id'],
                get_keys('etapestry',agcy=agcy),
                udf={
                    'Office Notes': '%s\n%s: non-participant (inactive for %s days)' %(
                    get_udf('Office Notes',acct), date.today().strftime('%b%-d %Y'))})

            gsheets.create_rfu(
              agency['name'],
              'Non-participant. No collection in %s days.' % agency['config']['non_participant_days'],
              a_id = np['id'],
              npu = npu,
              block = etap.get_udf('Block', np),
              _date = date.today().strftime('%-m/%-d/%Y'),
              driver_notes = etap.get_udf('Driver Notes', np),
              office_notes = etap.get_udf('Office Notes', np))

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def rfu(self, agency, note, **kwargs):
    from app import gsheets

    return gsheets.create_rfu(
        agency,
        note,
        a_id=kwargs['a_id'],
        npu=kwargs['npu'],
        block=kwargs['block'],
        _date=kwargs['_date'],
        name_addy=kwargs['name_addy'])

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_accts_sms(self, *args, **kwargs):
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
def add_gsheets_signup(self, *args, **kwargs):
    from app.main import signups
    signup = args[0] # FIXME

    try:
        return signups.add(signup)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())

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
    g.headers = get_row(g.service, g.ss_id, 1)

    for i in range(0, len(accts)):
        r = do_receipt(accts[i], entries[i])

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
        r = do_receipt(
            gift_accts[i]['account'],
            entries[i],
            gift_history=gift_histories[i])

    log.info('Gift receipts sent=%s', len(gift_accts))
