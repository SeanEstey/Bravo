'''app.main.tasks'''
import logging
from flask import g
from app import celery
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def non_participants(self, *args, **kwargs):
    '''Create RFU's for all non-participants on scheduled dates
    '''

    from app import cal
    from app.main import non_participants
    from . import etap, gsheets
    from datetime import date

    agencies = db['agencies'].find({})

    for agency in agencies:
        try:
            log.info('%s: Analyzing non-participants in 5 days...', agency['name'])

            accounts = cal.get_accounts(
                agency['etapestry'],
                agency['cal_ids']['res'],
                agency['google']['oauth'],
                days_from_now=5)

            if len(accounts) < 1:
                continue

            nps = non_participants.find(agency['name'], accounts)

            for np in nps:
                npu = etap.get_udf('Next Pickup Date', np)

                if len(npu.split('/')) == 3:
                    npu = etap.ddmmyyyy_to_mmddyyyy(npu)

                etap.call(
                    'modify_account',
                    agency['etapestry'], {
                        'id': np['id'],
                        'udf': {
                            'Office Notes': etap.get_udf('Office Notes', np) +\
                            '\n' + date.today().strftime('%b %-d %Y') + \
                            ': flagged as non-participant ' +\
                            ' (no collection in ' +\
                            str(agency['config']['non_participant_days']) + ' days)'

                        },
                        'persona':{}
                    }
                )

                gsheets.create_rfu(
                  agency['name'],
                  'Non-participant. No collection in %s days.' % agency['config']['non_participant_days'],
                  a_id = np['id'],
                  npu = npu,
                  block = etap.get_udf('Block', np),
                  _date = date.today().strftime('%-m/%-d/%Y'),
                  driver_notes = etap.get_udf('Driver Notes', np),
                  office_notes = etap.get_udf('Office Notes', np)
                )
        except Exception as e:
            log.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def send_receipts(self, entries, **rest):
    try:
        from app.main import receipts
        return receipts.process(entries)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())

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
    '''Celery Sub-task of API call 'send_receipts'
    Data sent from Routes worksheet in Gift Importer (Google Sheet)
    Celery process that sends email receipts to entries in Bravo
    Sheets->Routes worksheet. Lots of account data retrieved from eTap
    (accounts + journal data) so can take awhile to run 4 templates:
    gift_collection, zero_collection, dropoff_followup, cancelled entries:
    list of row entries to receive emailed receipts
    @entries: array of gift entries
    @etapestry_id: agency name and login info
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
    track = {
        'zeros': 0,
        'drop_followups': 0,
        'cancels': 0,
        'no_email': 0,
        'gifts': 0
    }

    gc = gsheets.auth(
        get_keys('google')['oauth'],
        ['https://spreadsheets.google.com/feeds'])
    wks = gc.open(current_app.config['GSHEET_NAME']).worksheet('Routes')
    headers = wks.row_values(1)

    with open('app/templates/schemas/%s.json' % g.user.agency) as json_file:
      schemas = json.load(json_file)['receipts']

    for i in range(0, len(accts)):
        r = do_receipt(
            accts[i],
            entries[i],
            wks, headers, track)

        if r == 'wait':
            gift_accts.append({
                'entry': entries[i], 'account': accts[i]})

    # All receipts sent except Gifts. Query Journal Histories

    if len(gift_accts) > 0:
        year = parse(gift_accts[0]['entry']['date']).year
        acct_refs = [i['account']['ref'] for i in gift_accts]
        gift_histories = get_je_histories(acct_refs, year)

        for i in range(0, len(gift_accts)):
            r = do_receipt(
                gift_accts[i]['account'],
                entries[i],
                wks, headers, track,
                gift_history=gift_histories[i])

    log.info('Receipts: \n' +
      str(num_zeros) + ' zero collections sent\n' +
      str(len(gift_accts)) + ' gift receipts sent\n' +
      str(num_drop_followups) + ' dropoff followups sent\n' +
      str(num_cancels) + ' cancellations sent\n' +
      str(num_no_emails) + ' no emails')
