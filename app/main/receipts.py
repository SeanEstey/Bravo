'''app.main.receipts'''
import gc, json
from datetime import datetime, date
from dateutil.parser import parse
from flask import g, render_template, request
from app import get_keys
from . import donors
from app.lib import html, mailgun
from app.main.parser import title_case
from app.lib.gsheets import get_headers, update_cell, write_cell, to_range, gauth, get_row
from app.lib.dt import ddmmyyyy_to_date as to_date, dt_to_ddmmyyyy
from .etap import call, get_udf
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def generate(acct, entry, ytd_gifts=None):
    '''Refer to flask globals set in parent task: g.ss_id, g.headers, g.track
    '''

    if not acct.get('ref'):
        log.error('Invalid account for receipt', extra={'account':acct})
        return {'mid':None, 'status':acct.get('message')}

    if not acct.get('email'):
        log.debug('skipping acct w/o email')
        g.track['no_email'] +=1
        return {'mid':None, 'status': 'No Email'}

    gift_date = parse(entry['date']).date()
    acct_status = get_udf('Status', acct)
    drop_date = get_udf('Dropoff Date', acct)
    drop_date = to_date(drop_date) if drop_date else None
    nf = acct['nameFormat']

    if entry['status'] == 'Cancelled':
        path = "receipts/%s/cancelled.html" % g.user.agency
        subject = "Your Account has been Cancelled"
        g.track['cancels'] +=1
    elif drop_date and drop_date == gift_date:
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
        path = "receipts/%s/collection_receipt.html" % g.user.agency
        subject = "Thanks for your Donation"
        g.track['gifts'] +=1
    else:
        raise Exception('Unknown receipt category')

    try:
        mid = deliver(
            acct['email'], path, subject,
            acct=acct, entry=entry, ytd_gifts=ytd_gifts)
    except Exception as e:
        result = {'status':'ERROR', 'desc':str(e)}
        log.exception('Row %s receipt error.',
            entry['ss_row'], extra={'result':result})
    else:
        result = {'status':'QUEUED', 'mid':mid}
        log.debug('Queued receipt to %s',
            acct['email'], extra={'result':result})

    return result

#-------------------------------------------------------------------------------
def render_body(path, acct, entry=None, ytd_gifts=None):
    '''Convert all dates in data to long format strings, render into html'''

    history = []

    if ytd_gifts:
        for gift in ytd_gifts:
            history.append({
                'date':gift['gift']['date'].strftime('%B %-d, %Y'),
                'amount': gift['gift']['amount']
            })

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
            history=history
        )
    except Exception as e:
        log.error('render receipt template: %s', str(e))
        return False

    return body

#-------------------------------------------------------------------------------
def preview(acct_id=None, type_=None):

    type_ = type_ if type_ else "donation"
    paths = {
        "donation": "receipts/%s/collection_receipt.html" % g.user.agency,
        "no_donation": "receipts/%s/no_collection.html" % g.user.agency,
        "zero_donation": "receipts/%s/zero_collection.html" % g.user.agency,
        "post_drop": "receipts/%s/dropoff_followup.html" % g.user.agency,
        "cancelled": "receipts/%s/cancelled.html" % g.user.agency
    }
    acct = donors.get(get_keys('admin')['pview_acct_id'])
    entry = {
        'acct_id': acct['id'],
        'date': date.today().strftime('%d/%m/%Y'),
        'amount':12.40,
        'next_pickup': get_udf('Next Pickup Date', acct),
        'status':'Active',
        'ss_row':2
    }

    body = render_body(
        paths[type_],
        acct,
        entry = entry,
        ytd_gifts = get_ytd_gifts(acct['ref'], date.today().year))

    return body

#-------------------------------------------------------------------------------
def deliver(to, template, subject, acct, entry=None, ytd_gifts=None):
    '''Sends a receipt/no collection/dropoff followup/etc for a route entry.
    Should be running in process() celery task
    Adds an eTapestry journal note with the content.
    '''

    body = render_body(template, acct, entry=entry, ytd_gifts=ytd_gifts)

    if body == False:
        log.error('no body returned from render_body')
        return False

    # Add Journal note
    call('add_note', data={
        'acct_id': acct['id'],
        'body': 'Receipt:\n' + html.clean_whitespace(body),
        'date': dt_to_ddmmyyyy(parse(entry['date']))
    })

    mid = mailgun.send(to, subject, body, get_keys('mailgun'),
        v={'ss_row':entry['ss_row'], 'agcy':g.user.agency, 'type':'receipt'})

    return mid

#-------------------------------------------------------------------------------
def get_ytd_gifts(acct_ref, year):
    '''Get non-zero gift entries for accts in given calendar year.
    Helper function for send_receipts task.
    @acct_refs: list of eTap acct DB refs
    '''

    if not acct_ref:
        return []

    gifts = g.db['cachedGifts'].find(
        {'gift.accountRef':acct_ref, 'gift.date': {'$gte':datetime(year, 1, 1)}})

    if not gifts:
        return []
    else:
        gifts = list(gifts)
        log.debug('Found %s cached gifts', len(gifts))
        return gifts

    """try:
        je_list = call('get_gift_histories', data={
            "acct_refs": [acct_ref],
            "start": "01/01/" + str(year),
            "end": "31/12/" + str(year)
        })
    except Exception as e:
        log.exception('Error retrieving donation history')
        return []
    else:
        return je_list[0]
    """

#-------------------------------------------------------------------------------
def on_delivered(agcy):
    '''Mailgun webhook called from view. Has request context'''

    g.group = agcy
    form = request.form
    keys = get_keys('google')
    log.debug('Receipt delivered to %s', form['recipient'])

    try:
        write_cell(keys['oauth'], keys['ss_id'], 'Donations', form['ss_row'], 'Receipt', form['event'].upper())
    except Exception as e:
        log.error('Failed to update receipt status')
    finally:
        service = None

#-------------------------------------------------------------------------------
def on_dropped(agcy):
    '''Mailgun webhook called from view. Has request context'''

    g.group = agcy
    form = request.form
    msg = 'Receipt to %s dropped. %s. %s' % (form['recipient'], form['reason'], form.get('description'))
    keys = get_keys('google')
    log.info(msg)

    try:
        write_cell(keys['oauth'], keys['ss_id'], 'Donations', form['ss_row'], 'Receipt', form['event'].upper())
    except Exception as e:
        log.error('Failed to update receipt status')
    finally:
        service = None

    from app.main.tasks import create_rfu
    create_rfu.delay(g.group, msg)
