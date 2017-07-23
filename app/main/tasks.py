# app.main.tasks

import json, logging
from datetime import datetime, date, time, timedelta as delta
from dateutil.parser import parse
from flask import current_app, g, request
from app import celery, get_keys
from celery import states
from celery.exceptions import Ignore
from app.lib.gsheets import to_range
from app.lib.timer import Timer
from .etapestry import call, get_acct, get_udf
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def _get_gifts(self, ref, start_date, end_date, cache=True, **rest):

    from app.main.etapestry import get_gifts
    log.debug('main.tasks._get_gifts')
    get_gifts(ref, parse(start_date), parse(end_date))

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def wipe_sessions(self, **rest):
    pass

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def receipt_handler(self, form, group, **rest):

    from googleapiclient.errors import HttpError
    from app.lib.gsheets_cls import SS
    from time import sleep
    import gc

    g.group = group
    keys = get_keys('google')
    log.debug('Receipt delivered to %s', form['recipient'])

    try:
        ss = SS(keys['oauth'], keys['ss_id'])
    except Exception as e:
        log.error('Failed to update Row %s.', form['ss_row'], extra={'desc':str(e)})
        gc.collect()
        self.update_state(state=states.FAILURE, meta=str(e))
        raise Ignore()
    else:
        wks = ss.wks('Donations')
        wks.updateCell(form['event'].upper(), row=form['ss_row'], col=3)
        gc.collect()

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_cache(self, **rest):

    from .etapestry import get_query

    BATCH_SIZE = 500
    series = [
        {'name':'vec', 'category':'BPU: Stats', 'query':'Recent Gifts', 'statsCount':'journalEntryCount'},
        {'name':'vec', 'category':'BPU: Stats', 'query':'Recent Accounts'}
    ]

    for group in series:
        g.group = group['name']
        timer = Timer()
        start = 0
        count = BATCH_SIZE
        queryEnd = False

        log.debug('Task: Caching Recent...')

        while queryEnd != True:
            results = get_query(
                group['query'],
                category=group['category'],
                start=start,
                count=count,
                cache=True,
                timeout=75)

            if len(results) == 0:
                queryEnd = True

            start += BATCH_SIZE

    log.debug('Task: Completed [%s]', timer.clock())

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def cache_gifts(self, **rest):
    """Cache Journal Entry Gifts
    """

    from .etapestry import get_query

    BATCH_SIZE = 500
    series = [
        {'name':'vec', 'category':'BPU: Stats', 'query':'Recent Gifts', 'statsCount':'journalEntryCount'},
        {'name':'vec', 'category':'BPU: Stats', 'query':'Recent Accounts'}
        #{'name':'wsf', 'category':'ETW: Stats', 'query':'Gift Entries [YTD]'}
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
                timeout=75)

            if len(results) == 0:
                break

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
def sys_health_check(self, **rest):
    """Check free mem on main Flask process
    """

    import requests
    r = requests.post("https://bravoweb.ca/health_check")

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
    from app.main.etapestry import get_query, get_udf
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

    # Search through cachedAccounts for geolocation matches.
    # Build list of Block queries to update cachedAccounts.
    queries = blocks
    n_no_geo = 0
    for cache in g.db['cachedAccounts'].find({'group':g.group}):
        acct = cache['account']
        geolocation = cache.get('geolocation')

        if not geolocation:
            n_no_geo +=1
            continue

        if in_map(geolocation['geometry']['location'], target_map):
            b = get_udf('Block', acct)
            if b:
                c = b.split(', ')
                for block in c:
                    if block not in queries:
                        queries.append(block)
                        log.debug('Added Block=%s', block)

    log.debug('Queries=%s', queries)

    matches = {}
    acct_list = []

    for query in queries:
        log.debug('Searching Query %s', query)

        try:
            accts = get_query(query)
        except Exception as e:
            log.exception('Error retrieving %s. Skipping', query)
            continue

        for acct in accts:
            geolocation = g.db['cachedAccounts'].find_one(
                {'group':g.group, 'account.id':acct['id']}
            ).get('geolocation')

            if not geolocation:
                log.debug('Skipping query acct w/o geolocation')
                continue

            pt = geolocation['geometry']['location']

            if in_map(pt, target_map):
                if acct['id'] not in matches:
                    matches[acct['id']] = acct
                    smart_emit('analyze_results',
                        {'status':'match','acct_id':acct['id'],'coords':pt,'n_matches':len(matches)})

    smart_emit('analyze_results', {'status':'completed','n_matches':len(matches)})

    # Write accounts to Bravo Sheets->Updater
    values = []
    for acct_id in matches:
        acct = matches[acct_id]
        values.append([
            '', '', zone, acct['id'], acct['address'], acct['name'],
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
def estimate_trend(self, date_str, ss_gifts, ss_id, ss_row, **rest):
    """@ss_gifts: list of orders from Bravo Sheets
    @ss_row: Route row on Stats SS to write result to.
    """

    from json import dumps
    from app.main.etapestry import get_journal_entries
    from app.lib.gsheets_cls import SS

    timer = Timer()
    ss_row = int(float(ss_row))
    route_d = parse(date_str).date()
    diff = 0
    n_repeat = 0

    log.info('Task: Analyzing estimate trend...',
        extra={'n_accts':len(ss_gifts), 'donations':dumps(ss_gifts,indent=2)})

    for ss_gift in ss_gifts:
        if not ss_gift['amount']:
            continue

        try:
            je_list = get_journal_entries(
                acct_id=ss_gift['acct_id'],
                start_d=route_d-delta(weeks=12),
                end_d=route_d,
                types=['Gift','Note'],
                cached=False)
        except Exception as e:
            continue

        if len(je_list) < 1:
            continue

        last_gift = 0.0

        for je in je_list:
            if je['type'] == 5:
                last_gift = float(je['amount'])
            elif je['type'] == 1 and je['note'] == 'No Pickup':
                last_gift = 0.0

        diff += float(ss_gift['amount']) - last_gift
        n_repeat += 1

    log.debug('n_repeat=%s, diff=%s', n_repeat, diff)

    if n_repeat == 0:
        n_repeat += 1

    trend = diff / n_repeat

    oauth = get_keys('google')['oauth']
    wks = SS(oauth, ss_id).wks('Daily')
    wks.updateCell(trend, row=ss_row, col_name='Estmt Trend')

    log.info('Task completed. Trend=$%.2f. [%s]', trend, timer.clock())

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def process_entries(self, entries, wks='Donations', col='Upload', **rest):
    '''Update accounts/upload donations, write results to Bravo Sheets.
    @entries: list of dicts w/ account fields/donations
    @wks: worksheet name
    @col: result column name
    '''

    from app.lib.gsheets_cls import SS
    from app.lib.gsheets import a1_range

    timer = Timer()
    CHK_SIZE = 10
    oauth = get_keys('google')['oauth']
    ss_id = get_keys('google')['ss_id']
    ss = SS(oauth, ss_id)
    headers = ss.wks(wks).getRow(1)
    ref_col = headers.index('Ref')+1
    upload_col = headers.index(col)+1

    log.info('Task: Processing %s account entries...', len(entries))

    chks = [entries[i:i + CHK_SIZE] for i in xrange(0, len(entries), CHK_SIZE)]
    task_start = datetime.utcnow()
    results = None

    for n in range(0,len(chks)):
        chk = chks[n]

        try:
            results = call('add_gifts', data={'entries':chk})
        except Exception as e:
            log.error('Error in chunk #%s. continuing...', n+1, extra={'description':e.message})
            results = "Failed to add gifts. Description: %s" % e.message
            continue
        else:
            # Build range/value for [REF, STATUS] pair
            ranges = []
            values = []
            for i in xrange(len(results)):
                ranges.append(
                    a1_range(results[i]['row'], ref_col, results[i]['row'], upload_col, wks=wks))
                values.append([[
                    results[i].get('ref', results[i].get('description')),
                    results[i]['status'].upper()]])

            #log.debug('Updating Sheet. Ranges=%s, values=%s', ranges, values)

            try:
                ss.wks(wks).updateRanges(ranges, values)
            except Exception as e:
                log.exception('Error writing chunk %s', n+1)
            else:
                log.debug('Chunk %s/%s uploaded/written to Sheets.', n+1, len(chks))
        finally:
            g.db['taskResults'].update_one(
                {'group':g.group, 'task':'process_entries', 'started': task_start},
                {'$push': {'results':{
                    'chunk': '%s/%s' % (n+1, len(chks)),
                    'results': results,
                    'n_entries':len(results) if type(results) is list else "N/A",
                    'completed':datetime.utcnow(),
                    'duration':timer.clock(stop=False)
                }}},
                upsert=True)

    update_cache.delay()
    """
    # TODO: update cachedAccounts
    for entry in entries:
        cached = g.db['cachedAccounts'].find_one({'account.id':entry['acct_id']})
        # entry['udf']: {'Status':VAL, 'Next Pickup Date':VAL}
    """

    log.info('Task completed. %s entries processed. [%s]', len(entries), timer.clock())

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
    from app.lib.gsheets_cls import SS
    from app.lib.gsheets import a1_range
    from app.main.donors import ytd_gifts
    from app.main.receipts import get_template, deliver

    timer = Timer()
    oauth = get_keys('google')['oauth']
    ss_id = get_keys('google')['ss_id']
    receipts = [] # Master list holding receipting data
    ss_gifts = json.loads(ss_gifts)

    log.info('Task: Processing %s receipts...', len(ss_gifts))

    for ss_gift in ss_gifts:
        receipt = {
            'account': get_acct(ss_gift['acct_id']),
            'ss_gift': ss_gift
        }
        if receipt['account'].get('email'):
            template = get_template(receipt['account'], ss_gift)
            year = parse(ss_gift['date']).date().year

            receipt.update({
                'path': template['path'],
                'subject': template['subject'],
                'ytd_gifts': ytd_gifts(receipt['account']['ref'], year)
            })
        receipts.append(receipt)

    ss = SS(oauth, ss_id)
    status_col = ss.wks('Donations').getRow(1).index('Receipt')+1
    n_queued = 0
    sublists = split_list(receipts, sub_len=10) # Break-up for batch updating Sheet

    # Deliver receipts in batches

    for i in xrange(0, len(sublists)):
        sublist = sublists[i]
        ranges = []
        values = []

        for receipt in sublist:
            account = receipt['account']

            if not account.get('email'):
                receipt['result'] = {'status':'NO EMAIL'}
            else:
                try:
                    result = deliver(account, receipt['ss_gift'], receipt['ytd_gifts'])
                except Exception as e:
                    log.exception('Failed to send receipt to %s', account.get('email'))
                    receipt['result'] = {
                        'status':'ERROR',
                        'desc':e.message,
                        'ss_gift':receipt['ss_gift']
                    }
                else:
                    receipt['result'] = result
                    n_queued += 1

            # Build range/value for each cell in case rows are discontinuous
            row = receipt['ss_gift']['ss_row']
            ranges.append(a1_range(row,status_col,row,status_col, wks='Donations'))
            values.append([[receipt['result']['status']]])

        #log.debug('Updating Sheet. Ranges=%s, Values=%s', ranges, values)

        # Update 'Receipt' column with status
        try:
            ss.wks('Donations').updateRanges(ranges, values)
        except Exception as e:
            log.exception('Error updating receipt values')
        else:
            log.debug('Updated Donations->Receipt column')

    errs = [r['result'] for r in receipts if r['result']['status'] == 'ERROR']

    log.info('Receipts queued=%s. Errors=%s [%s]',
        n_queued, len(errs), timer.clock(stop=False))

    health_check()

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
def create_accounts(self, accts_json, group=None, **rest):
    '''Upload accounts + send welcome email, send status to Bravo Sheets
    @accts_json: JSON list of form data
    '''

    from app.lib.gsheets_cls import SS
    from app.lib.gsheets import a1_range

    timer = Timer()
    g.group = group
    accts = json.loads(accts_json)
    log.info('Task: Creating %s accounts...', len(accts))

    # Break accts into chunks for gsheets batch updating
    ch_size = 10
    chks = [accts[i:i + ch_size] for i in xrange(0, len(accts), ch_size)]
    log_rec = {
        'n_success': 0,
        'n_errs': 0,
        'errors':[]}

    ss = SS(get_keys('google')['oauth'], get_keys('google')['ss_id'])
    wks = ss.wks('Signups')
    headers = wks.getRow(1)
    ref_col = headers.index('Ref')+1
    upload_col = headers.index('Upload')+1

    for i in range(0, len(chks)):
        rv = []
        chk = chks[i]

        try:
            rv = call('add_accts', data={'accts':chk})
        except Exception as e:
            log.exception('Error adding accounts')
            log_rec['errors'].append(e)

        # Build range/value for [REF, STATUS] pair
        ranges = []
        values = []
        res = rv['results']
        for n in xrange(len(res)):
            ranges.append(a1_range(res[n]['ss_row'], ref_col, res[n]['ss_row'], upload_col, wks='Signups'))
            values.append([[res[n].get('ref',''), res[n]['status'].upper()]])

        #log.debug('Updating Sheet. Ranges=%s, values=%s', ranges, values)

        try:
            wks.updateRanges(ranges, values)
        except Exception as e:
            log.exception('Error writing to Bravo Sheets.')
        else:
            log.debug('Chunk %s/%s written to Sheets', i+1, len(chks))

        # rv = {'n_success':<int>, 'n_errs':<int>, 'results':[ {'row':<int>, 'status':<str>}, ... ]
        log.debug('rv=%s', rv)
        log_rec['n_success'] += int(rv['n_success'])

        if int(rv['n_errs']) > 0:
            log_rec['n_errs'] += int(rv['n_errs'])
            log_rec['errors'].append(rv['results'])

    log_rec['duration'] = timer.clock()

    if log_rec['n_errs'] > 0:
        log.error('Task completed. %s/%s accounts created. See Bravo Sheets for details.',
            log_rec['n_success'], log_rec['n_success']+log_rec['n_errs'],
            extra=log_rec)
    else:
        log.info('Task completed. %s/%s accounts created. [%s]',
            log_rec['n_success'], log_rec['n_success'] + log_rec['n_errs'], timer.clock(),
            extra=log_rec)


    update_cache.delay()

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def create_rfu(self, group, note, options=None, **rest):

    from app.lib.gsheets_cls import SS

    g.group = group
    ss = SS(get_keys('google')['oauth'], get_keys('google')['ss_id'])
    wks = ss.wks('Issues')
    headers = wks.getRow(1)

    rfu = [''] * len(headers)
    rfu[headers.index('Description')] = note
    rfu[headers.index('Type')] = 'Followup'
    rfu[headers.index('Resolved')] = 'No'
    rfu[headers.index('Date')] = date.today().strftime("%m-%d-%Y")

    for field in headers:
        if options and field in options:
            rfu[headers.index(field)] = options[field]

    wks.appendRows([rfu])
    log.debug('Creating RFU=%s', rfu)
    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_calendar(self, from_=date.today(), group=None, **rest):
    '''Update all calendar blocks in date period with booking size/color codes.
    @from_, to_: datetime.date
    '''

    from .parser import get_block, is_bus, get_area, is_route_size
    from app.lib.gcal import gauth, color_ids, get_events, evnt_date_to_dt, update_event
    from app.lib.dt import d_to_dt

    groups = [get_keys(group=group)] if group else g.db['groups'].find()
    start_dt = d_to_dt(from_)
    today = date.today()
    timer = Timer()
    d_str = '%m-%d-%Y'

    for group_ in groups:
        g.group = group_['name']
        end_dt = d_to_dt(today + delta(days=get_keys('main')['cal_block_delta_days']))
        srvc = gauth(get_keys('google')['oauth'])
        cal_ids = get_keys('cal_ids')
        n_updated = n_errs = n_warnings = 0

        log.warning('Updating calendar events...',
            extra={'start': start_dt.strftime(d_str), 'end': end_dt.strftime(d_str)})

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
                        'category': get_keys('etapestry')['query_category'],
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
def find_inactive_donors(self, group=None, in_days=5, period_=None, **rest):
    '''Create RFU's for all non-participants on scheduled dates
    '''

    from app.lib.dt import ddmmyyyy_to_mmddyyyy as swap_dd_mm
    from .schedule import get_accounts
    from .donors import is_inactive
    from .etapestry import mod_acct

    groups = [get_keys(group=group)] if group else g.db['groups'].find()
    n_task_inactive = 0
    timer = Timer()

    for group_ in groups:
        accts = []
        acct_matches = []
        n_inactive = 0
        g.group = group_['name']

        log.warning('Identifying inactive donors...')

        cal_ids = group_['cal_ids']
        period = period_ if period_ else group_['donors']['inactive_period']
        on_date = date.today() + delta(days=in_days)

        log.info('Analyzing inactive donors on %s routes...', on_date.strftime('%m-%d'),
            extra={'inactive_period (days)': period})

        for _id in cal_ids:
            accts += get_accounts(cal_ids[_id], delta_days=in_days)

        if len(accts) < 1:
            continue

        for acct in accts:
            try:
                res = is_inactive(acct, days=period)
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

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def update_leaderboard_accts(self, group=None, **rest):

    from .schedule import get_blocks
    from .leaderboard import update_accts, update_gifts

    g.group=group
    log.warning('Updating leaderboards...')
    groups = [get_keys(group=group)] if group else g.db['groups'].find()
    timer = Timer()

    for group_ in groups:
        g.group = group_['name']

        # Get list of all scheduled blocks from calendar
        blocks = get_blocks(
            get_keys('cal_ids')['routes'], # FIXME. only works for VEC
            datetime.now(),
            datetime.now() + delta(weeks=10),
            get_keys('google')['oauth'])

        for query in blocks:
            update_accts(query, g.group)

        # Now update gifts
        accts = list(g.db['accts_cache'].find({'group':g.group}))
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
def add_form_signup(self, data, **rest):

    g.group = 'wsf'
    from app.main.signups import add_etw_to_gsheets

    try:
        add_etw_to_gsheets(data)
    except Exception as e:
        log.exception('Error writing signup to Bravo Sheets.')
        raise

    return 'success'
