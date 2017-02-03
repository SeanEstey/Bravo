'''app.main.receipts'''
import json, logging, requests
from datetime import date
from dateutil.parser import parse
from flask import g, current_app, render_template, request
from .. import get_keys, html, mailgun, etap
from app.gsheets import update_cell, to_range, gauth, get_row
from app.etap import get_udf
from app.dt import ddmmyyyy_to_date as to_date, dt_to_ddmmyyyy
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def generate(acct, entry, ytd_gifts=None):
    '''Refer to flask globals set in parent task: g.service, g.ss_id,
    g.headers, g.track
    '''

    #log.debug('generate receipt for agcy=%s', g.user.agency)

    gift_date = parse(entry['date']).date()
    acct_status = get_udf('Status', acct)
    drop_date = to_date(get_udf('Dropoff Date', acct))
    nf = acct['nameFormat']

    if entry['status'] == 'Cancelled':
        path = "receipts/%s/cancelled.html" % g.user.agency
        subject = "Your Account has been Cancelled"
        g.track['cancels'] +=1
    elif drop_date == gift_date:
        path = "receipts/%s/dropoff_followup.html" % g.user.agency
        subject = "Dropoff Complete"
        g.track['drops'] +=1
    elif entry['amount'] == 0 and nf == 3:
        path = "receipts/%s/zero_collection.html" % g.user.agency
        subject = "See you next time"
        g.track['zeros'] +=1
    elif entry['amount'] == 0 and nf < 3:
        path = "receipts/%s/no_collection.html" % g.user.agency
        subject = "See you next time"
        g.track['zeros'] +=1
    elif entry['amount'] > 0:
        if ytd_gifts:
            path = "receipts/%s/collection_receipt.html" % g.user.agency
            subject = "Thanks for your Donation"
        else:
            return 'wait'

    if acct['email']:
        try:
            mid = deliver(acct['email'], path, subject, acct=acct, entry=entry, ytd_gifts=ytd_gifts)
        except Exception as e:
            log.error('receipt error. Row %s: %s',str(entry['ss_row']), str(e))

        status = 'queued'
    else:
        g.track['no_email'] +=1
        status = 'no email'

    log.debug('receipt sent. mid=%s', mid)

    return {'mid':mid, 'status':'queued'}

#-------------------------------------------------------------------------------
def on_delivered(agcy):
    '''Mailgun webhook called from view. Has request context'''

    log.info('receipt delivered to %s', request.form['recipient'])

    row = request.form['ss_row']
    ss_id = get_keys('google',agcy=agcy)['ss_id']

    try:
        service = gauth(get_keys('google',agcy=agcy)['oauth'])
        headers = get_row(service, ss_id, 'Routes', 1)
        col = headers.index('Email Status')+1
        update_cell(service, ss_id, to_range(row,col), request.form['event'])
    except Exception as e:
        log.error('error updating sheet')

#-------------------------------------------------------------------------------
def on_dropped(agcy):
    '''Mailgun webhook called from view. Has request context'''
    from app.main.tasks import create_rfu

    row = request.form['ss_row']
    msg = 'receipt to %s dropped. %s. %s' %(
        request.form['recipient'],
        request.form['reason'],
        request.form.get('description'))

    log.info(msg)

    ss_id = get_keys('google',agcy=agcy)['ss_id']

    try:
        service = gauth(get_keys('google',agcy=agcy)['oauth'])
        headers = get_row(service, ss_id, 'Routes', 1)
        col = headers.index('Email Status')+1
        update_cell(service, ss_id, to_range(row,col), request.form['event'])
    except Exception as e:
        log.error('error updating sheet')

    create_rfu.delay(agcy, msg, options={
        'Date': date.today().strftime('%-m/%-d/%Y')})

#-------------------------------------------------------------------------------
def render_body(path, acct, entry=None, ytd_gifts=None):
    '''Convert all dates in data to long format strings, render into html'''

    # Bravo php returned gift histories as ISOFormat
    if ytd_gifts:
        for je in ytd_gifts:
            je['date'] = parse(je['date']).strftime('%B %-d, %Y')

    # Entry dates are in ISOFormat string. Convert to long format
    if entry:
        entry['date'] = parse(entry['date']).strftime('%B %-d, %Y')

        if entry.get('next_pickup'):
            npu = parse(entry['next_pickup'])
            entry['next_pickup'] = npu.strftime('%B %-d, %Y')

    try:
        body = render_template(
            path,
            to= acct['email'],
            account= acct,
            entry= entry,
            history= ytd_gifts)
    except Exception as e:
        log.error('render receipt template: %s', str(e))
        return False

    return body

#-------------------------------------------------------------------------------
def deliver(to, template, subject, acct, entry=None, ytd_gifts=None):
    '''Sends a receipt/no collection/dropoff followup/etc for a route entry.
    Should be running in process() celery task
    Adds an eTapestry journal note with the content.
    '''

    #log.debug('%s %s', str(data['account']['id']), template)

    body = render_body(template, acct, entry=entry, ytd_gifts=ytd_gifts)

    if body == False:
        log.error('no body returned from render_body')
        return False

    # Add Journal note
    etap.call(
        'add_note',
        get_keys('etapestry'),
        data={
            'acct_id': acct['id'],
            'body': 'Receipt:\n' + html.clean_whitespace(body),
            'date': dt_to_ddmmyyyy(parse(entry['date']))})

    mid = mailgun.send(to, subject, body, get_keys('mailgun'),
        v={'ss_row':entry['ss_row'], 'agcy':g.user.agency, 'type':'receipt'})

    return mid

#-------------------------------------------------------------------------------
def get_ytd_gifts(acct_ref, year):
    '''Get non-zero gift entries for accts in given calendar year.
    Helper function for send_receipts task.
    @acct_refs: list of eTap acct DB refs
    '''

    try:
        je_list = etap.call(
            'get_gift_histories',
            get_keys('etapestry'),
            data={
                "acct_refs": [acct_ref],
                "start": "01/01/" + str(year),
                "end": "31/12/" + str(year)})
    except Exception as e:
        log.error('Error retrieving gift histories: %s', str(e))
        raise
    else:
        return je_list[0]
