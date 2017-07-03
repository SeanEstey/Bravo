'''app.main.tasks'''
import json, logging
from datetime import datetime, date, time, timedelta as delta
from dateutil.parser import parse
from flask import current_app, g, request
from app import celery, get_keys
from app.lib.dt import d_to_dt, ddmmyyyy_to_mmddyyyy as swap_dd_mm
from app.lib.gsheets import gauth, write_rows, append_row, get_row, to_range,\
get_values, update_cell
from app.lib.gcal import gauth as gcal_auth, color_ids, get_events, evnt_date_to_dt, update_event
from app.lib.timer import Timer
from .parser import get_block, is_block, is_res, is_bus, get_area, is_route_size
from .cal import get_blocks, get_accounts
from .etap import call, get_acct, get_udf, mod_acct, get_query
from . import donors
from .leaderboard import update_accts, update_gifts
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def _get_gifts(self, ref, start_date, end_date, cache=True, **rest):
    from app.main.etap import get_gifts
    log.debug('main.tasks._get_gifts')
    get_gifts(ref, parse(start_date), parse(end_date))

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def wipe_sessions(self, **rest):
    pass

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def cache_gifts(self, **rest):
    """Cache Journal Entry Gifts
    TODO: Create query for WSF
    """

    BATCH_SIZE = 500

    series = [
        {'name':'vec', 'category':'BPU: Stats', 'query':'Gift Entries [YTD]'},
        {'name':'wsf', 'category':'ETW: Stats', 'query':'Gift Entries [YTD]'}
    ]

    for group in series:
        g.group = group['name']
        timer = Timer()
        start = 0
        count = BATCH_SIZE
        n_total = call(
            'getQueryResultStats',
            data={'queryName':group['query'], 'queryCategory':group['category']},
            timeout=0
        )['journalEntryCount']

        log.info('Task: Caching gifts [Total: %s]...', n_total)

        while start < n_total:
            results = get_query(
                group['query'],
                category=group['category'],
                start=start,
                count=count,
                cache=True,
                timeout=60)

            log.debug('Retrieved %s/%s gifts', start+count, n_total)

            start += BATCH_SIZE

            if start + count > n_total:
                count = start + count - n_total

    log.info('Task: Completed [%s]', timer.clock())

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def backup_mongo(self, **rest):

    from db_auth import user, password
    import os
    os.system("mongodump -u %s -p %s -o ~/Dropbox/mongo" %(user,password))
    log.warning('MongoDB backup created')

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def health_check(self, **rest):

    from app.lib.utils import mem_check
    import gc
    mem = mem_check()

    if mem['free'] < 350:
        import gc, os
        log.debug('Low memory. %s/%s. forcing gc/clearing cache...',
            mem['free'], mem['total'])
        os.system('sudo sysctl -w vm.drop_caches=3')
        os.system('sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches')
        gc.collect()
        mem2 = mem_check()
        log.debug('Freed %s mb', mem2['free'] - mem['free'])

        if mem2['free'] < 350:
            log.warning('Warning: low memory! 250mb recommended (%s/%s)',
                mem2['free'], mem['total'])

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def find_zone_accounts(self, zone=None, blocks=None, **rest):
    '''Called from API via client user.'''

    from app.lib.gsheets_cls import SS
    from app.main.etap import get_query
    from app.main.maps import geocode, in_map
    from app.main.socketio import smart_emit

    log.info('Task: Searching zone matches...',
        extra={'blocks':blocks, 'map':zone})

    timer = Timer()
    target_map = None

    for m in g.db.maps.find_one({'agency':g.group})['features']:
        if zone == m['properties']['name']:
            target_map = m
            break

    if not target_map:
        log.error('map not found')
        return 'failed'

    api_key = get_keys('google')['geocode']['api_key']
    matches = []

    for block in blocks:
        log.debug('Searching Block %s', block)

        try:
            accts = get_query(block)
        except Exception as e:
            log.exception('Error retrieving %s. Skipping', block)
            continue

        for acct in accts:
            geolocation = g.db['cachedAccounts'].find_one(
                {'group':g.group, 'account.id':acct['id']}
            ).get('geolocation')

            if not geolocation:
                continue

            pt = geolocation['geometry']['location']

            if in_map(pt, target_map):
                matches.append(acct)
                smart_emit('analyze_results',
                    {'status':'match','acct_id':acct['id'],'coords':pt,'n_matches':len(matches)})

    smart_emit('analyze_results', {'status':'completed','n_matches':len(matches)})

    # Write accounts to Bravo Sheets->Updater

    values = []

    for acct in matches:
        values.append([
            '', zone, acct['id'], acct['address'], acct['name'],
            get_udf('Block',acct), get_udf('Neighborhood',acct), get_udf('Status',acct),
            get_udf('Signup Date',acct), get_udf('Next Pickup Date',acct),
            get_udf('Driver Notes',acct), get_udf('Office Notes',acct)
        ])

    try:
        ss = SS(get_keys('google')['oauth'], get_keys('google')['ss_id'])
        wks = ss.wks("Accounts")
        wks.appendRows(values)
    except Exception as e:
        log.exception('Error writing to Sheet')

    log.info('Task completed. %s zone matches found. [%s]', len(matches), timer.clock())
    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_leaderboard_accts(self, agcy=None, **rest):

    g.group=agcy
    log.warning('Updating leaderboards...')
    agcy_list = [get_keys(agcy=agcy)] if agcy else g.db['groups'].find()
    timer = Timer()

    for agency in agcy_list:
        g.group = agency['name']

        # Get list of all scheduled blocks from calendar
        blocks = get_blocks(
            get_keys('cal_ids',agcy=g.group)['routes'], # FIXME. only works for VEC
            datetime.now(),
            datetime.now() + delta(weeks=10),
            get_keys('google',agcy=g.group)['oauth'])

        for query in blocks:
            update_accts(query, g.group)

        # Now update gifts
        accts = list(g.db['accts_cache'].find({'agcy':g.group}))
        ch_size = 100
        chks = [accts[i:i + ch_size] for i in xrange(0, len(accts), ch_size)]

        for n in range(0,len(chks)):
            chk = chks[n]
            update_gifts(chk, g.group)

        log.warning('Updated leaderboards', extra={'duration':timer.clock()})

        timer.restart()

    # Duration: ~1277s for 2900 accts
    g.group = None

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def estimate_trend(self, date_str, donations, ss_id, ss_row, **rest):

    from json import dumps
    timer = Timer()
    ss_row = int(float(ss_row))
    route_d = parse(date_str).date()
    diff = 0
    n_repeat = 0

    log.info('Task: Analyzing estimate trend...',
        extra={'n_accts':len(donations), 'donations':dumps(donations,indent=2)})

    for donation in donations:
        if not donation['amount']:
            continue

        try:
            je_hist = donors.get_donations(
                donation['acct_id'],
                start_d = route_d - delta(weeks=12),
                end_d = route_d)
        except Exception as e:
            continue

        if len(je_hist) < 1:
            #log.debug('skipping acct w/ je len < 1')
            continue

        diff += float(donation['amount']) - je_hist[0]['amount']
        n_repeat += 1

    log.debug('n_repeat=%s, diff=%s', n_repeat, diff)

    if n_repeat == 0:
        n_repeat += 1

    trend = diff / n_repeat

    service = gauth(get_keys('google')['oauth'])
    headers = get_row(service, ss_id, 'Daily', 1)

    update_cell(
        service,
        ss_id,
        'Daily',
        to_range(ss_row, headers.index('Estmt Trend')+1),
        diff/n_repeat)

    log.info('Task completed. Trend=$%.2f. [%s]', diff/n_repeat, timer.clock())

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def process_entries(self, entries, wks='Donations', col='Upload', **rest):
    '''Update accounts/upload donations, write results to Bravo Sheets.
    @entries: list of dicts w/ account fields/donations
    @wks: worksheet name
    @col: result column name
    '''

    CHK_SIZE = 10
    SUCCESS = [u'Processed', u'Updated']

    log.info('Task: Processing %s account entries...', len(entries))

    timer = Timer()
    chks = [entries[i:i + CHK_SIZE] for i in xrange(0, len(entries), CHK_SIZE)]
    ss_id = get_keys('google')['ss_id']
    srvc = gauth(get_keys('google')['oauth'])
    headers = get_row(srvc, ss_id, wks, 1)
    rv_col = headers.index(col) +1
    n_errs = 0

    for n in range(0,len(chks)):
        chk = chks[n]
        try:
            r = call('process_entries', data={'entries':chk})
        except Exception as e:
            log.error('error in chunk #%s. continuing...', n+1)
            continue
        else:
            results = r['results']
            n_errs += r['n_errs']
            range_ = '%s:%s' %(
                to_range(results[0]['row'], rv_col),
                to_range(results[-1]['row'], rv_col))
            values = [[results[i]['status']].upper() for i in range(len(results))]

            #for i in range(len(values)):
            #    value = values[i][0]
            #    values[i][0] = value.upper() if value in SUCCESS else results[i].get('description','')

        try:
            write_rows(srvc, ss_id, wks, range_, values)
        except Exception as e:
            log.exception('Error writing chunk %s', n+1)
        else:
            log.debug('Chunk %s/%s uploaded/written to Sheets.', n+1, len(chks),
                extra={'n_success':r['n_success'], 'n_errs':r['n_errs']})

    # Now update cachedAccounts
    for entry in entries:
        cached = g.db['cachedAccounts'].find_one({'account.id':entry['acct_id']})
        # entry['udf']: {'Status':VAL, 'Next Pickup Date':VAL}

    log.info('Task completed. %s entries processed. [%s]',
        len(entries), timer.clock(), extra={'n_errs':n_errs})
    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def send_receipts(self, ss_gifts, **rest):
    """Email receipts from Bravo Sheets inputs.

    @ss_gifts: input list with format {acct_id:INT, date:DD/MM/YYYY, amount:FLOAT,
    next_pickup:DD/MM/YYYY, status:STR, ss_row:INT}
    """

    from app.lib.html import no_ws
    from app.lib.dt import dt_to_ddmmyyyy
    from app.lib.utils import split_list
    from app.lib.gsheets import get_header_column
    from app.main.donors import ytd_gifts
    from app.main.receipts import get_template, deliver

    timer = Timer()
    ss_gifts = json.loads(ss_gifts)

    log.info('Task: Processing %s receipts...', len(ss_gifts))

    receipts = [] # Master list holding receipting data

    for ss_gift in ss_gifts:
        receipt = {
            'account': get_acct(ss_gift['acct_id']),
            'ss_gift': ss_gift
        }
        if receipt['account']['email']:
            template = get_template(receipt['account'], ss_gift)
            year = parse(ss_gift['date']).date().year

            receipt.update({
                'path': template['path'],
                'subject': template['subject'],
                'ytd_gifts': ytd_gifts(receipt['account']['ref'], year)
            })
        receipts.append(receipt)

    oauth = get_keys('google')['oauth']
    ss_id = get_keys('google')['ss_id']
    wks = 'Donations'
    status_col = get_header_column(oauth, ss_id, wks, 'Receipt')
    n_queued = 0
    sublists = split_list(receipts, sub_len=10) # Break-up for batch updating Sheet

    # Deliver receipts in batches

    for i in xrange(0, len(sublists)):
        sublist = sublists[i]

        for receipt in sublist:
            account = receipt['account']

            if not account.get('email'):
                receipt['result'] = {'status':'NO EMAIL'}
                continue

            try:
                result = deliver(account, receipt['ss_gift'], receipt['ytd_gifts'])
            except Exception as e:
                log.exception('Failed to send receipt to %s', account['email'])
                receipt['result'] = {
                    'status':'ERROR',
                    'desc':e.message,
                    'ss_gift':receipt['ss_gift']
                }
            else:
                receipt['result'] = result
                n_queued += 1

        # Update "Receipt" Sheet column values

        a1_start = to_range(sublist[0]['ss_gift']['ss_row'], status_col)
        a1_end = to_range(sublist[-1]['ss_gift']['ss_row'], status_col)
        try:
            write_rows(
                gauth(oauth), ss_id, wks,
                '%s:%s' % (a1_start, a1_end),
                [[r['result']['status']] for r in sublist]
            )
        except Exception as e:
            log.exception('Error updating receipt values')
        else:
            log.debug('Updated Donations->Receipt column')

    errs = [r['result'] for r in receipts if r['result']['status'] == 'ERROR']

    log.info('Receipts queued=%s. Errors=%s [%s]',
        n_queued, len(errs), timer.clock(stop=False))

    # Add Journal Contact Notes

    for receipt in receipts:
        if receipt['result']['status'] != 'QUEUED':
            continue

        date_str = dt_to_ddmmyyyy(parse(receipt['ss_gift']['date']))
        body = 'Receipt:\n%s' % no_ws(receipt['result']['body'])
        call('add_note', data={
            'acct_id': receipt['account']['id'],
            'body': body,
            'date': date_str
        })

    log.info('Task completed. Journal Contacts added. [%s]',
        timer.clock(), extra={'errors':errs})

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def create_accounts(self, accts_json, agcy=None, **rest):
    '''Upload accounts + send welcome email, send status to Bravo Sheets
    @accts_json: JSON list of form data
    '''

    CHECKMK = u'\u2714'
    timer = Timer()
    g.group = agcy
    accts = json.loads(accts_json)
    log.info('Task: Creating %s accounts...', len(accts))
    # Break accts into chunks for gsheets batch updating
    ch_size = 10
    chks = [accts[i:i + ch_size] for i in xrange(0, len(accts), ch_size)]
    log_rec = {
        'n_success': 0,
        'n_errs': 0,
        'errors':[]}

    ss_id = get_keys('google')['ss_id']
    service = gauth(get_keys('google')['oauth'])
    headers = get_row(service, ss_id, 'Signups', 1)

    for i in range(0, len(chks)):
        rv = []
        chk = chks[i]

        try:
            rv = call('add_accts', data={'accts':chk})
        except Exception as e:
            log.exception('Error adding accounts')
            log_rec['errors'].append(e)

        # rv = {'n_success':<int>, 'n_errs':<int>, 'results':[ {'row':<int>, 'status':<str>}, ... ]
        log.debug('rv=%s', rv)
        log_rec['n_success'] += int(rv['n_success'])

        if int(rv['n_errs']) > 0:
            log_rec['n_errs'] += int(rv['n_errs'])
            log_rec['errors'].append(rv['results'])

        range_ = '%s:%s' %(
            to_range(chk[0]['ss_row'], headers.index('Ref')+1),
            to_range(chk[-1]['ss_row'], headers.index('Upload')+1))

        values = [[rv['results'][idx].get('ref'), rv['results'][idx]['status']]
            for idx in range(0, len(rv['results']))
        ]

        #for j in range(len(values)):
        #    if values[j][2] == u'Uploaded':
        #        values[j][2] = 'COMPLETED' #CHECKMK

        try:
            write_rows(service, ss_id, 'Signups', range_, values)
        except Exception as e:
            log.exception('Error writing to Bravo Sheets.')
        else:
            log.debug('Chunk %s/%s written to Sheets', i+1, len(chks))

    log_rec['duration'] = timer.clock()

    if log_rec['n_errs'] > 0:
        log.error('Task completed. %s/%s accounts created. See Bravo Sheets for details.',
            log_rec['n_success'], log_rec['n_success']+log_rec['n_errs'],
            extra=log_rec)
    else:
        log.info('Task completed. %s/%s accounts created. [%s]',
            log_rec['n_success'], log_rec['n_success'] + log_rec['n_errs'], timer.clock(),
            extra=log_rec)
    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def create_rfu(self, agcy, note, options=None, **rest):

    g.group = agcy
    srvc = gauth(get_keys('google')['oauth'])
    ss_id = get_keys('google')['ss_id']
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
def update_calendar_blocks(self, from_=date.today(), agcy=None, **rest):
    '''Update all calendar blocks in date period with booking size/color codes.
    @from_, to_: datetime.date
    '''

    agcy_list = [get_keys(agcy=agcy)] if agcy else g.db['groups'].find()
    start_dt = d_to_dt(from_)
    today = date.today()
    timer = Timer()
    d_str = '%m-%d-%Y'

    for agency in agcy_list:
        g.group = agency['name']
        end_dt = d_to_dt(today + delta(days=get_keys('main')['cal_block_delta_days']))
        etap_conf = get_keys('etapestry')
        oauth = get_keys('google')['oauth']
        srvc = gcal_auth(oauth)

        log.warning('Updating calendar events...',
            extra={'start': start_dt.strftime(d_str), 'end': end_dt.strftime(d_str)
        })

        cal_ids = get_keys('cal_ids')
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
                    rv = call('get_route_size', data={
                        'category': etap_conf['query_category'],
                        'query': block,
                        'date':dt.strftime('%d/%m/%Y')})
                except Exception as e:
                    log.exception('Error retrieving query for %s', block)
                    n_errs+=1
                    continue

                # Title format: 'R6B [Area1, Area2, Area3] (51/55)'

                if not is_route_size(rv):
                    log.debug('invalid value=%s from "get_route_size"', rv)
                    n_errs+=1
                    continue

                if not evnt.get('location'):
                    log.debug('missing postal codes in event="%s"', evnt['summary'])
                    n_warnings+=1

                new_title = '%s [%s] (%s)' %(
                    get_block(title), get_area(title) or '', rv)

                n_booked = int(rv[0:rv.find('/')])

                if is_bus(block):
                    sizes = current_app.config['BLOCK_SIZES']['BUS']
                else:
                    sizes = current_app.config['BLOCK_SIZES']['RES']

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
                    log.exception(str(e))
                    n_errs+=1
                else:
                    n_updated+=1
        extra= {
            'n_events': n_updated,
            'n_errs': n_errs,
            'n_warnings': n_warnings,
            'duration': timer.clock()
        }
        if n_errs > 0:
            log.error('Calendar events updated. %s errors.', n_errs, extra=extra)
        else:
            log.warning('Calendar events updated.', extra=extra)

        timer.restart()

    g.group = None
    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_accts_sms(self, agcy=None, in_days=None, **rest):
    '''Verify that all accounts in upcoming residential routes with mobile
    numbers are set up to interact with SMS system'''

    from . import sms

    days = in_days if in_days else 3
    agcy_list = [get_keys(agcy=agcy)] if agcy else g.db['groups'].find()
    accts = []

    for agency in agcy_list:
        g.group = agency['name']
        cal_ids = get_keys('cal_ids',agcy=g.group)
        for _id in cal_ids:
            # Get accounts scheduled on Residential routes 3 days from now
            accts += get_accounts(cal_ids[_id], delta_days=days)

        if len(accts) < 1:
            return 'failed'

        r = sms.enable(agency['name'], accts)

        log.info('Updated %s accounts for SMS. Discovered %s mobile numbers.',
            r['n_sms'], r['n_mobile'])

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def add_form_signup(self, data, **rest):

    g.group = 'wsf'
    log.debug('received ETW form submission. data=%s', data)
    from app.main.signups import add_etw_to_gsheets

    try:
        add_etw_to_gsheets(data)
    except Exception as e:
        log.exception('Error writing signup to Bravo Sheets.')
        raise

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def find_inactive_donors(self, agcy=None, in_days=5, period_=None, **rest):
    '''Create RFU's for all non-participants on scheduled dates
    '''

    agcy_list = [get_keys(agcy=agcy)] if agcy else g.db['groups'].find()
    n_task_inactive = 0
    timer = Timer()

    for agency in agcy_list:
        accts = []
        acct_matches = []
        n_inactive = 0
        g.group = agency['name']

        log.warning('Identifying inactive donors...')

        cal_ids = agency['cal_ids']
        period = period_ if period_ else agency['donors']['inactive_period']
        on_date = date.today() + delta(days=in_days)

        log.info('Analyzing inactive donors on %s routes...', on_date.strftime('%m-%d'),
            extra={'inactive_period (days)': period})

        for _id in cal_ids:
            accts += get_accounts(cal_ids[_id], delta_days=in_days)

        if len(accts) < 1:
            continue

        for acct in accts:
            try:
                res = donors.is_inactive(acct, days=period)
            except Exception as e:
                continue
            else:
                if res == False:
                    continue

            acct_matches.append({'id':acct['id'], 'name':acct.get('name','')})
            npu = get_udf('Next Pickup Date', acct)

            if len(npu.split('/')) == 3:
                npu = swap_dd_mm(npu)

            mod_acct(
                acct['id'],
                udf={
                    'Office Notes': '%s\n%s: Inactive for %s days'%(
                        get_udf('Office Notes', acct),
                        date.today().strftime('%b %-d %Y'),
                        period)
                },
                exc=False)

            create_rfu(
                g.group,
                'Non-participant. No collection in %s days.' % period,
                options={
                    'ID': acct['id'],
                    'Next Pickup': npu,
                    'Block': get_udf('Block', acct),
                    'Driver Notes': get_udf('Driver Notes', acct),
                    'Office Notes': get_udf('Office Notes', acct)})

            n_inactive += 1

        log.info('Found %s inactive donors.', n_inactive,
            extra={'matches':acct_matches, 'n_sec':timer.clock()})

        n_task_inactive += n_inactive
        timer.restart()

    g.group = None
    log.warning('Inactive Donors task completed. %s accounts found.', n_task_inactive)
    return 'success'
