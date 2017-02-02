'''app.main.tasks'''
import json, logging, re
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from flask import g
from app import cal, celery, get_keys
from app.parser import get_block, is_block, get_area, is_route_size
from app.gcal import gauth as gcal_auth, get_events, to_dt, rename_event
from app.cal import get_blocks
from app.gsheets import gauth, append_row, get_row
from app.etap import call, get_udf, mod_acct
from app.dt import ddmmyyyy_to_mmddyyyy as swap_dd_mm
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def find_inactive_donors(self, agcy=None, in_days=5, period=None, **rest):
    '''Create RFU's for all non-participants on scheduled dates
    '''

    import app.main.donors

    if agcy:
        agencies = [g.db.agencies.find_one({'name':agcy})]
    else:
        agencies = g.db.agencies.find({})

    for agency in agencies:
        agcy = agency['name']
        if not period:
            period = agency['config']['non_participant_days']
        log.info('%s: Analyzing non-participants in 5 days...', agcy)

        accts = cal.get_accounts(
            agency['etapestry'],
            agency['cal_ids']['res'],
            agency['google']['oauth'],
            days_from_now=in_days)

        if len(accts) < 1:
            continue

        for acct in accts:
            if not donors.is_inactive(agcy, acct, days=period):
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
                    period)})

            create_rfu(
                agcy,
                'Non-participant. No collection in %s days.' % period,
                options={
                    'Account Number': acct['id'],
                    'Next Pickup Date': npu,
                    'Block': get_udf('Block', acct),
                    'Date': date.today().strftime('%-m/%-d/%Y'),
                    'Driver Notes': get_udf('Driver Notes', acct),
                    'Office Notes': get_udf('Office Notes', acct)})

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_calendar_blocks(self, agcy='vec', **rest):
    '''Update calendar events for each Block with num accounts booked and total
    Block size
    '''

    log.info('task: updating calendar route sizes...')

    if agcy:
        agencies = [g.db.agencies.find_one({'name':agcy})]
    else:
        agencies = g.db.agencies.find({})

    for agency in agencies:
        agcy = agency['name']
        etap_conf = get_keys('etapestry',agcy=agcy)
        oauth = get_keys('google',agcy=agcy)['oauth']
        srvc = gcal_auth(oauth)

        start = datetime.combine(date.today(), time())
        end = start + timedelta(days=30)
        cal_ids = get_keys('cal_ids',agcy=agcy)

        n_updated = n_errs = 0

        for id_ in cal_ids:
            events = get_events(srvc, cal_ids[id_], start, end)

            for evnt in events:
                dt = to_dt(evnt['start']['date'])
                block = get_block(evnt['summary'])
                title = evnt['summary']

                if not block:
                    continue

                try:
                    rv = call('get_route_size', etap_conf, {
                        'category': etap_conf['query_category'],
                        'query': block,
                        'date':dt.strftime('%d/%m/%Y')})
                except Exception as e:
                    n_errs+=1
                    continue

                # Title format: 'R6B [Area1, Area2, Area3] (51/55)'

                if not is_route_size(rv):
                    log.debug('invalid value=%s from "get_route_size"', rv)
                    n_errs+=1
                    continue

                new_title = '%s [%s] (%s)' %(
                    get_block(title), get_area(title) or '', rv)

                log.debug('updating block %s event title="%s", date=%s',
                    block, new_title, evnt['start']['date'])

                rename_event(srvc, cal_ids[id_], evnt['id'],
                    evnt['start']['date'], evnt['end']['date'], new_title)
                n_updated+=1

                '''
                if is_res(block):
                    DO_ME = ''
                    #booking_size = booking_rules['size']['res'];
                else:
                    DO_ME = ''
                    #booking_size = booking_rules['size']['bus'];

                if(size < booking_size['medium'])
                  new_event['colorId'] = Settings['calendar_color_id']['green'];
                else if(size >= booking_size['medium'] && size < booking_size['large'])
                  new_event['coloured'] = Settings['calendar_color_id']['yellow'];
                else if(size >= booking_size['large'] && size < booking_size['max'])
                  new_event['colorId'] = Settings['calendar_color_id']['orange'];
                else if(size >= booking_size['max'])
                  new_event['colorId'] = Settings['calendar_color_id']['light_red'];
                '''

        log.info('updated %s calendar events. %s errors. agcy=%s', n_updated, n_errs, agcy)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def send_receipts(self, entries, **rest):
    '''Email receipts to recipients and update email status on Bravo Sheets.
    Sheets->Routes worksheet.
    @entries: array of gift entry dicts->
        {'amount':float, 'date':str,'from':{'row':int,'upload_status':str(db_ref),'worksheet':str}}
    '''

    entries = json.loads(entries)
    log.info('processing receipts...')

    #log.debug('tasks.send_receipts entries=%s, type=%s', entries, type(entries))
    from app.main.receipts import generate, get_ytd_gifts

    try:
        # Get all eTapestry account data.
        # List is indexed the same as @entries arg list
        accts = call(
            'get_accts',
            get_keys('etapestry'),
            {"acct_ids": [i['acct_id'] for i in entries]})
    except Exception as e:
        log.error('Error retrieving accounts from etap: %s', str(e))
        raise

    gift_accts = []
    g.track = {
        'zeros': 0,
        'drops': 0,
        'cancels': 0,
        'no_email': 0,
        'gifts': 0}
    g.ss_id = get_keys('google')['ss_id']
    g.service = gauth(get_keys('google')['oauth'])
    g.headers = get_row(g.service, g.ss_id, 'Routes', 1)

    for i in range(0, len(accts)):
        r = generate(accts[i], entries[i])

        if r == 'wait':
            gift_accts.append({
                'entry': entries[i], 'account': accts[i]})

    log.info('sent zero_collections=%s, dropoff_followups=%s, cancels=%s. '\
        '%s accts without email', g.track['zeros'], g.track['drops'],
        g.track['cancels'], g.track['no_email'])

    # All receipts sent except Gifts. Query Journal Histories

    if len(gift_accts) == 0:
        log.info('no gift receipts to send')
        return 'success'

    try:
        year = parse(gift_accts[0]['entry']['date']).year
        acct_refs = [i['account']['ref'] for i in gift_accts]
        gift_histories = get_ytd_gifts(acct_refs, year)
    except Exception as e:
        log.error(str(e))
        log.debug('', exc_info=True)
        raise

    for i in range(0, len(gift_accts)):
        try:
            r = generate(
                gift_accts[i]['account'],
                gift_accts[i]['entry'],
                gift_history=gift_histories[i])
        except Exception as e:
            log.error('generate receipt error. desc=%s', str(e))
            log.debug('',exc_info=True)
            continue

    log.info('sent gift receipts=%s', len(gift_accts))

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def create_rfu(self, agcy, note, options=None, **rest):

    srvc = gauth(get_keys('google',agcy=agcy)['oauth'])
    ss_id = get_keys('google',agcy=agcy)['ss_id']
    wks = 'RFU'
    headers = get_row(srvc, ss_id, wks, 1)
    rfu = [''] * len(headers)
    rfu[headers.index('Request Note')] = note

    log.debug(headers)
    log.debug(options)

    for field in headers:
        if field in options:
            rfu[headers.index(field)] = options[field]

    append_row(srvc, ss_id, wks, rfu)
    log.debug('Creating RFU=%s', rfu)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_accts_sms(self, agcy=None, in_days=None, **rest):
    '''Verify that all accounts in upcoming residential routes with mobile
    numbers are set up to interact with SMS system'''

    from . import sms

    if not in_days:
        in_days = 3

    if agcy:
        agencies = [db.agencies.find_one({'name':agcy})]
    else:
        agencies = db.agencies.find({})

    for agency in agencies:
        # Get accounts scheduled on Residential routes 3 days from now
        accounts = cal.get_accounts(
            agency['etapestry'],
            agency['cal_ids']['res'],
            agency['google']['oauth'],
            days_from_now=in_days)

        if len(accounts) < 1:
            return 'failed'

        r = sms.enable(agency['name'], accounts)

        log.info('%supdated %s accounts for SMS. discovered %s mobile numbers%s',
                    bcolors.OKGREEN, r['n_sms'], r['n_mobile'], bcolors.ENDC)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def add_gsheets_signup(self, data, **rest):
    from app.main import signups
    signup = args[0] # FIXME

    try:
        signups.add(signup)
    except Exception as e:
        log.error('error adding signup. desc="%s"', str(e))
        log.debug('', exc_info=True)
        raise

    return 'success'
