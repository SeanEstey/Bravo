'''app.main.receipts'''
import json, logging, os, requests
from datetime import date
from dateutil.parser import parse
from flask import current_app, render_template, request
from .. import get_keys, html, mailgun, etap, gsheets
from app.main.tasks import create_rfu
from app.gsheets import update_cell, a1
from app.etap import get_udf, ddmmyyyy_to_date as to_date
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def on_delivered():
    '''Mailgun webhook called from view. Has request context'''

    log.info('receipt delivered to %s', request.form['recipient'])

    email = g.db.emails.find_one_and_update(
        {'mid': request.form['Message-Id']},
        {'$set': {'status': request.form['event']}})
    agcy = email['agency']
    service = gsheets.gauth(get_keys('google',agcy=agcy)['oauth'])
    headers = gsheets.get_values(
        service,
        get_keys('google',agcy=agcy)['ss_id'],
        'Routes!1:1'
    )[0]

    if 'Email Status' not in headers:
        log.error('Missing "Email Status" header')
        return False

    col_a1 = gsheets.col_idx_to_a1(headers.index('Email Status'))

    gsheets.update_cell(
        service,
        get_keys('google',agcy=agcy)['ss_id'],
        'Routes!' + col_a1 + str(email['on_status']['update']['row']),
        request.form['event']
    )

#-------------------------------------------------------------------------------
def on_dropped():
    '''Mailgun webhook called from view. Has request context'''

    msg = 'receipt to %s dropped. %s. %s' %(
        request.form['recipient'],
        request.form['reason'],
        request.form.get('description'))

    log.info(msg)

    email = g.db['emails'].find_one_and_update(
        {'mid': request.form['Message-Id']},
        {'$set': {'status': request.form['event']}})

    gsheets.update_entry(
      email['agency'],
      request.form['event'],
      email['on_status']['update']
    )

    create_rfu.delay(
        email['agency'],
        msg,
        options={
            'Date': date.today().strftime('%-m/%-d/%Y')})

#-------------------------------------------------------------------------------
def render_body(path, data):
    '''Convert all dates in data to long format strings, render into html'''

    # Bravo php returned gift histories as ISOFormat
    if data.get('history'):
        for gift in data['history']:
            gift['date'] = parse(gift['date']).strftime('%B %-d, %Y')

    # Entry dates are in ISOFormat string. Convert to long format
    if data.get('entry'):
        data['entry']['date'] = parse(data['entry']['date']).strftime('%B %-d, %Y')

        if data['entry'].get('next_pickup'):
            npu = parse(data['entry']['next_pickup'])
            data['entry']['next_pickup'] = npu.strftime('%B %-d, %Y')

    try:
        body = render_template(
            path,
            to = data['account']['email'],
            account = data['account'],
            entry = data['entry'],
            history = data.get('history'), # optional
            http_host= os.environ.get('BRAVO_HTTP_HOST')
        )
    except Exception as e:
        log.error('render receipt template: %s', str(e))
        return False

    return body

#-------------------------------------------------------------------------------
def deliver(to, template, subject, data):
    '''Sends a receipt/no collection/dropoff followup/etc for a route entry.
    Should be running in process() celery task
    Adds an eTapestry journal note with the content.
    '''

    log.debug('%s %s', str(data['account']['id']), template)

    body = render_body(template, data=data)

    if body == False:
        return False

    # Add Journal note
    etap.call(
        'add_note',
        get_keys('etapestry'),
        data={
            'id': data['account']['id'],
            'Note': 'Receipt:\n' + html.clean_whitespace(body),
            'Date': etap.dt_to_ddmmyyyy(parse(data['entry']['date']))
        },
        silence_exceptions=False
    )

    mid = mailgun.send(to, subject, body, get_keys('mailgun'), v={'type':'receipt'})

    g.db.emails.insert_one({
        'agency': g.user.agency,
        'mid': mid,
        'type': 'receipt',
        'on_status': {
            'update': data['entry']['from']}})

#-------------------------------------------------------------------------------
def generate(acct, entry, gift_history=None):
    '''Refer to flask globals set in parent task: g.service, g.ss_id,
    g.headers, g.track
    '''

    entry_date = parse(entry['date']).date()
    acct_status = get_udf('Status', acct)
    drop_date = to_date(get_udf('Dropoff Date', acct))
    nf = account['nameFormat']

    if acct_status == 'Cancelled':
        path = "receipts/%s/cancelled.html" % g.user.agency
        subject = "Your Account has been Cancelled"
    elif drop_date == entry_date:
        path = "receipts/%s/dropoff_followup.html" % g.user.agency
        subject = "Dropoff Complete"
        g.track['drop_followups'] +=1
    elif entry['amount'] == 0 and nf == 3:
        path = "receipts/%s/zero_collection.html" % g.user.agency
        subject = "See you next time"
        g.track['num_zeros'] +=1
    elif entry['amount'] == 0 and nf < 3:
        path = "receipts/%s/no_collection.html" % g.user.agency
        subject = "See you next time"
        g.track['num_zeros'] +=1
    elif entry['amount'] > 0:
        if gift_history:
            path = "receipts/%s/collection_receipt.html" % g.user.agency
            subject = "Thanks for your Donation"
        else:
            return 'wait'

    if acct['email']:
        try:
            deliver(acct['email'], path, subject, data={
                'account':acct,'entry':entry,'history':gift_history})
        except Exception as e:
            log.error('Receipt error. Row %s: %s',str(entry['from']['row']), str(e))

        status = 'queued'
    else:
        g.track['no_email'] +=1
        status = 'no email'

    row = entry['from']['row']
    col = headers.index('Email Status')+1

    try:
        update_cell(g.service, g.ss_id, a1(row,col), status)
    except Exception as e:
        log.error('update_cell error')

#-------------------------------------------------------------------------------
def get_gifts_ytd(acct_refs, year):
    '''Get non-zero gift entries for accts in given calendar year.
    Helper function for send_receipts task.
    @acct_refs: list of eTap acct DB refs
    '''

    try:
        je_list = etap.call(
            'get_gift_histories',
            get_keys('etapestry'),
            data={
                "account_refs": acct_refs,
                "start_date": "01/01/" + str(year),
                "end_date": "31/12/" + str(year)
            })
    except Exception as e:
        log.error('Error retrieving gift histories: %s', str(e))
        raise
    else:
        log.info('%s gift histories retrieved', str(len(je_list)))
        return je_list
