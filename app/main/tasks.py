'''app.main.tasks'''
import gc, json, logging, os, re, requests, psutil
from guppy import hpy
from pprint import pformat
from datetime import datetime, date, time, timedelta as delta
from dateutil.parser import parse
from flask import current_app, g, request
from app import celery, get_keys, task_logger
from app.lib.logger import colors as c
from app.lib.dt import d_to_dt, ddmmyyyy_to_mmddyyyy as swap_dd_mm
from app.lib.gsheets import gauth, write_rows, append_row, get_row, to_range, get_values
from app.lib.gcal import gauth as gcal_auth, color_ids, get_events, evnt_date_to_dt, update_event
from app.lib.utils import start_timer, end_timer
from .parser import get_block, is_block, is_res, is_bus, get_area, is_route_size
from .cal import get_blocks, get_accounts
from .etap import call, get_udf, mod_acct
from . import donors
from .receipts import generate, get_ytd_gifts
log = task_logger('main.tasks')

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def mem_check(self, **rest):

    t = datetime.now().time()

    # Restart celery worker at midnight to release memory leaks
    if t.hour == 0 and t.minute <=15:
        log.debug('restarting celery worker/beat at midnight...')
        try:
            r = requests.get('http://bravotest.ca/restart_worker')
        except Exception as e:
            log.debug(str(e))
        else:
            log.debug('code=%s, text=%s', r.status_code, r.text)

    mem = psutil.virtual_memory()
    total = (mem.total/1000000)
    free = mem.free/1000000

    if free < 350:
        log.debug('low memory. %s/%s. forcing gc/clearing cache...', free, total)
        os.system('sudo sysctl -w vm.drop_caches=3')
        os.system('sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches')
        gc.collect()
        mem = psutil.virtual_memory()
        total = (mem.total/1000000)
        now_free = mem.free/1000000
        log.debug('freed %s mb', now_free - free)

        if free < 350:
            log.warning('warning: low memory! 250mb recommended (%s/%s)', free, total)
    else:
        log.debug('mem free: %s/%s', free,total)

    return mem

#-------------------------------------------------------------------------------
def mem_snap(hp, snap=None):
    if snap is None:
        before = hp.heap()
        log.debug('m1 snap')
        return before

    log.debug('m2 snap')

    try:
        after = hp.heap()
        leftover = after - snap
        byrcs = leftover.byrcs
        log.debug(str(byrcs[0])) #:10])
        log.debug(str(byrcs.byid[0])) #:10])
    except Exception as e:
        pass

    #import pdb; pdb.set_trace()

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def process_entries(self, entries, agcy=None, **rest):

    entries = json.loads(entries)

    log.warning('processing %s gift entries...', len(entries))

    wks = 'Donations'
    checkmark = u'\u2714' #"=char(10004)"
    ch_size = 10
    etap_conf = get_keys('etapestry',agcy=agcy)
    chunks = [entries[i:i + ch_size] for i in xrange(0, len(entries), ch_size)]

    ss_id = get_keys('google',agcy=agcy)['ss_id']
    srvc = gauth(get_keys('google',agcy=agcy)['oauth'])
    headers = get_row(srvc, ss_id, wks, 1)
    upload_col = headers.index('Upload') +1
    n_success = n_errs = 0

    for n in range(0,len(chunks)):
        chunk = chunks[n]
        log.debug('processing chunk %s/%s...', n+1, len(chunks))
        try:
            r = call(
                'process_entries',
                etap_conf,
                {'entries':chunk})
        except Exception as e:
            log.error('error in chunk #%s. continuing...', n+1)
            continue

        log.debug('chunk processed. n_success=%s, n_errs=%s',
            r['n_success'], r['n_errs'])

        n_success += r['n_success']
        n_errs += r['n_errs']

        range_ = '%s:%s' %(
            to_range(r['results'][0]['row'], upload_col),
            to_range(r['results'][-1]['row'], upload_col))

        log.debug('writing chunk %s/%s return values to ss, range=%s',
            n+1, len(chunks), range_)

        values = [[r['results'][i]['status']] for i in range(len(r['results']))]

        for i in range(len(values)):
            if values[i][0] == u'Processed' or values[i][0] == u'Updated':
                values[i][0] = checkmark
            elif values[i][0] == u'Failed':
                values[i][0] = r['results'][i]['description']

        try:
            write_rows(srvc, ss_id, wks, range_, values)
        except Exception as e:
            log.error(str(e))
            log.debug('',exc_info=True)

    log.warning('completed. %s errors.', n_errs)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_calendar_blocks(self, from_=date.today(), to=date.today()+delta(days=30), agcy=None, **rest):
    '''Update all calendar blocks in date period with booking size/color codes.
    @from_, to_: datetime.date
    '''

    agcy_list = [get_keys(agcy=agcy)] if agcy else g.db.agencies.find()
    start_dt = d_to_dt(from_)
    end_dt = d_to_dt(to)

    for agency in agcy_list:
        agcy = agency['name']
        etap_conf = get_keys('etapestry',agcy=agcy)
        oauth = get_keys('google',agcy=agcy)['oauth']
        srvc = gcal_auth(oauth)

        log.warning('updating calendar events from %s to %s...',
            start_dt.strftime('%m-%d-%Y'), end_dt.strftime('%m-%d-%Y'))

        cal_ids = get_keys('cal_ids',agcy=agcy)
        n_updated = n_errs = n_warnings = 0

        for id_ in cal_ids:
            events = get_events(srvc, cal_ids[id_], start_dt, end_dt)

            for evnt in events:
                dt = evnt_date_to_dt(evnt['start']['date'])
                block = get_block(evnt['summary'])
                title = evnt['summary']

                if not block:
                    log.debug('invalid event title="%s"', evnt['summary'])
                    n_warnings+=1
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

                if not evnt.get('location'):
                    log.debug('missing postal codes in event="%s"',
                    evnt['summary'])
                    n_warnings+=1

                new_title = '%s [%s] (%s)' %(
                    get_block(title), get_area(title) or '', rv)

                n_booked = int(rv[0:rv.find('/')])

                if is_res(block):
                    sizes = current_app.config['BLOCK_SIZES']['RES']
                else:
                    sizes = current_app.config['BLOCK_SIZES']['BUS']

                color_id = None

                if n_booked < sizes['MED']:
                    color_id = color_ids['green']
                elif (n_booked >= sizes['MED']) and (n_booked < sizes['LRG']):
                    color_id = color_ids['yellow']
                elif (n_booked >= sizes['LRG']) and (n_booked < sizes['MAX']):
                    color_id = color_ids['orange']
                elif n_booked >= sizes['MAX']:
                    color_id = color_ids['light_red']

                try:
                    update_event(srvc, evnt, title=new_title, color_id=color_id)
                except Exception as e:
                    n_errs+=1
                else:
                    n_updated+=1

        log.warning('completed. %s events updated, %s errors, %s warnings '\
            '(agcy=%s)', n_updated, n_errs, n_warnings, agcy)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def send_receipts(self, entries, **rest):
    '''Email receipts to recipients and update email status on Bravo Sheets.
    Sheets->Routes worksheet.
    @entries: list of dicts: {
        'acct_id':'<int>', 'date':'dd/mm/yyyy', 'amount':'<float>',
        'next_pickup':'dd/mm/yyyy', 'status':'<str>', 'ss_row':'<int>' }
    '''

    start = start_timer()
    entries = json.loads(entries)
    wks = 'Donations'
    checkmark = u'\u2714' #"=char(10004)"
    log.warning('processing %s receipts...', len(entries))

    try:
        # list indexes match @entries
        accts = call(
            'get_accts',
            get_keys('etapestry'),
            {"acct_ids": [i['acct_id'] for i in entries]})
    except Exception as e:
        log.error('Error retrieving accounts from etap: %s', str(e))
        raise

    accts_data = [{
        'acct':accts[i],
        'entry':entries[i],
        'ytd_gifts':get_ytd_gifts(
            accts[i].get('ref'),
            parse(entries[i].get('date')).year)
    } for i in range(0,len(accts))]

    g.track = {
        'zeros': 0,
        'drops': 0,
        'cancels': 0,
        'no_email': 0,
        'gifts': 0
    }
    g.ss_id = get_keys('google')['ss_id']
    service = gauth(get_keys('google')['oauth'])
    g.headers = get_row(service, g.ss_id, wks, 1)
    status_col = g.headers.index('Receipt') +1

    # Break entries into equally sized lists for batch updating google sheet

    ch_size = 10
    chunks = [accts_data[i:i + ch_size] for i in xrange(0, len(accts_data), ch_size)]
    log.debug('chunk length=%s', len(chunks))

    for i in range(0, len(chunks)):
        rv = []
        chunk = chunks[i]
        for acct_data in chunk:
            rv.append(generate(
                acct_data['acct'],
                acct_data['entry'],
                ytd_gifts=acct_data['ytd_gifts']))

        range_ = '%s:%s' %(
            to_range(chunk[0]['entry']['ss_row'], status_col),
            to_range(chunk[-1]['entry']['ss_row'], status_col))

        values = [[rv[idx]['status']] for idx in range(len(rv))]
        curr_values = get_values(service, g.ss_id, wks, range_)

        for row_idx in range(0, len(curr_values)):
            if curr_values[row_idx][0] == checkmark:
                values[row_idx][0] = checkmark
            elif values[row_idx][0] == 'No Email':
                values[row_idx][0] = 'No Email'
            else:
                values[row_idx][0] = '...'

        log.debug('writing chunk %s/%s values to ss, range=%s',
            i+1, len(chunks), range_)

        try:
            write_rows(service, g.ss_id, wks, range_, values)
        except Exception as e:
            log.error(str(e))
            log.debug('',exc_info=True)

    duration = end_timer(start)

    log.warning(\
        'completed. sent gifts=%s, zeros=%s, post_drops=%s, cancels=%s, no_email=%s (%ss)',
        g.track['gifts'], g.track['zeros'], g.track['drops'],
        g.track['cancels'], g.track['no_email'], duration)

    chunks = acct_data = accts = None
    gc.collect()
    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def create_accounts(self, accts_json, agcy=None, **rest):
    '''Upload accounts + send welcome email, send status to Bravo Sheets
    @accts_json: JSON list of form data
    '''

    accts = json.loads(accts_json)
    log.warning('creating %s accounts...', len(accts))
    checkmark = u'\u2714' #"=char(10004)"
    ss_id = get_keys('google', agcy=agcy)['ss_id']
    service = gauth(get_keys('google', agcy=agcy)['oauth'])
    headers = get_row(service, ss_id, 'Signups', 1)
    status_col = headers.index('Upload') +1
    n_errs = n_success = 0

    # Break accts into chunks for gsheets batch updating

    ch_size = 10
    chunks = [accts[i:i + ch_size] for i in xrange(0, len(accts), ch_size)]
    log.debug('chunk length=%s', len(chunks))

    for i in range(0, len(chunks)):
        rv = []
        chunk = chunks[i]

        try:
            rv = call('add_accts', get_keys('etapestry', agcy=agcy), {'accts':chunk})
        except Exception as e:
            log.error('add_accts. desc=%s', str(e))
            log.debug('', exc_info=True)

        # rv = {'n_success':<int>, 'n_errs':<int>, 'results':[ {'row':<int>, 'status':<str>}, ... ]

        n_errs += int(rv['n_errs'])
        n_success += int(rv['n_success'])

        log.debug('rv=%s', rv)

        range_ = '%s:%s' %(
            to_range(chunk[0]['ss_row'], status_col),
            to_range(chunk[-1]['ss_row'], status_col))

        values = [[rv['results'][idx]['status']] for idx in range(0, len(rv['results']))]

        for j in range(len(values)):
            if values[j][0] == u'Uploaded':
                values[j][0] = checkmark

        log.debug('writing chunk %s/%s values to ss, range=%s',
            i+1, len(chunks), range_)

        try:
            write_rows(service, ss_id, 'Signups', range_, values)
        except Exception as e:
            log.error(str(e))
            log.debug('',exc_info=True)

    log.warning('completed. %s accounts created, %s errors.', n_success, n_errs)

    chunks = accts = None
    gc.collect()
    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def create_rfu(self, agcy, note, options=None, **rest):

    srvc = gauth(get_keys('google',agcy=agcy)['oauth'])
    ss_id = get_keys('google',agcy=agcy)['ss_id']
    headers = get_row(srvc, ss_id, 'Issues', 1)

    rfu = [''] * len(headers)
    rfu[headers.index('Description')] = note
    rfu[headers.index('Type')] = 'Followup'
    rfu[headers.index('Resolved')] = 'No'
    rfu[headers.index('Date')] = date.today().strftime("%m-%d-%Y")

    for field in headers:
        if options and field in options:
            rfu[headers.index(field)] = options[field]

    append_row(srvc, ss_id, 'Issues', rfu)
    log.debug('Creating RFU=%s', rfu)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_accts_sms(self, agcy=None, in_days=None, **rest):
    '''Verify that all accounts in upcoming residential routes with mobile
    numbers are set up to interact with SMS system'''

    from . import sms

    days = in_days if in_days else 3
    agcy_list = [get_keys(agcy=agcy)] if agcy else g.db.agencies.find()
    accts = []

    for agency in agcy_list:
        cal_ids = get_keys('cal_ids',agcy=agency['name'])
        for _id in cal_ids:
            # Get accounts scheduled on Residential routes 3 days from now
            accts += get_accounts(
                agency['etapestry'],
                cal_ids[_id],
                agency['google']['oauth'],
                days_from_now=days)

        if len(accts) < 1:
            return 'failed'

        r = sms.enable(agency['name'], accts)

        log.info('%supdated %s accounts for SMS. discovered %s mobile numbers%s',
                    c.GRN, r['n_sms'], r['n_mobile'], c.ENDC)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def add_form_signup(self, data, **rest):
    log.debug('received ETW form submission. data=%s', data)
    from app.main.signups import add_etw_to_gsheets

    try:
        add_etw_to_gsheets(data)
    except Exception as e:
        log.error('error adding signup. desc="%s"', str(e))
        log.debug('', exc_info=True)
        raise

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def find_inactive_donors(self, agcy=None, in_days=5, period_=None, **rest):
    '''Create RFU's for all non-participants on scheduled dates
    '''

    log.warning('identifying inactive donors...')

    agcy_list = [get_keys(agcy=agcy)] if agcy else g.db.agencies.find()
    n_task_inactive = 0

    for agency in agcy_list:
        accts = []
        n_inactive = 0
        agcy = agency['name']
        cal_ids = agency['cal_ids']
        period = period_ if period_ else agency['donors']['inactive_period']
        on_date = date.today() + delta(days=in_days)

        log.info('analyzing blocks on %s blocks (period=%s days, agcy=%s)...',
            on_date.strftime('%m-%d-%Y'), period, agcy)

        for _id in cal_ids:
            accts += get_accounts(
                agency['etapestry'],
                cal_ids[_id],
                agency['google']['oauth'],
                days_from_now=in_days)

        if len(accts) < 1:
            continue

        for acct in accts:
            try:
                res = donors.is_inactive(agcy, acct, days=period)
            except Exception as e:
                continue
            else:
                if res == False:
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
                    period)},
                exc=False)

            create_rfu(
                agcy,
                'Non-participant. No collection in %s days.' % period,
                options={
                    'ID': acct['id'],
                    'Next Pickup': npu,
                    'Block': get_udf('Block', acct),
                    'Driver Notes': get_udf('Driver Notes', acct),
                    'Office Notes': get_udf('Office Notes', acct)})

            n_inactive += 1

        log.info('found %s accounts', n_inactive)

        n_task_inactive += n_inactive

    log.warning('completed. %s inactive accounts identified', n_task_inactive)
    return 'success'
