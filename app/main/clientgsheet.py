"""app.main.clientgsheet
"""

#-------------------------------------------------------------------------------
def process_entries(entries, wks='Donations', col='upload'):
    '''Update accounts/upload donations, write results to Bravo Sheets.
    @entries: list of dicts w/ account fields/donations
    @wks: worksheet name
    @col: result column name
    '''

    from app.lib.gsheets_cls import SS, a1_range

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

    update_recent_cache.delay(group=g.group)
    """
    # TODO: update cachedAccounts
    for entry in entries:
        cached = g.db['cachedAccounts'].find_one({'account.id':entry['acct_id']})
        # entry['udf']: {'Status':VAL, 'Next Pickup Date':VAL}
    """

    log.info('Task completed. %s entries processed. [%s]', len(entries), timer.clock())

    return 'success'

#-------------------------------------------------------------------------------
def send_receipts(ss_gifts):
    """Email receipts from Bravo Sheets inputs.

    @ss_gifts: input list with format {acct_id:INT, date:DD/MM/YYYY, amount:FLOAT,
    next_pickup:DD/MM/YYYY, status:STR, ss_row:INT}
    """

    from app.lib.html import no_ws
    from app.lib.dt import dt_to_ddmmyyyy
    from app.lib.utils import split_list
    from app.lib.gsheets_cls import SS, a1_range
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
def receipt_status_handler(form, group):

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
