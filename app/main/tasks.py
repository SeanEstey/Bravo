'''app.main.tasks'''

import logging
from flask import g
from app.tasks import celery_sio, celery
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
def send_receipts(self, *args, **kwargs):
    entries = args[0] # FIXME
    etapestry_id = args[1] # FIXME

    try:
        from app.main import receipts
        return receipts.process(entries, etapestry_id)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def rfu(self, *args, **kwargs):
    from app import gsheets

    agency = args[0] # FIXME
    note = args[1] # FIXME

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
def add_signup(self, *args, **kwargs):
    signup = args[0] # FIXME
    try:
        from app import wsf
        return wsf.add_signup(signup)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())
