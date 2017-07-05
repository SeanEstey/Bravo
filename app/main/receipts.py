'''app.main.receipts'''
import gc, json
from datetime import datetime, date
from dateutil.parser import parse
from flask import g, render_template, request
from app import get_keys
from . import donors
from app.lib.utils import mem_check
from app.lib import html, mailgun
from app.main.parser import title_case
from app.lib.gsheets import get_headers, update_cell, write_cell, to_range, gauth, get_row
from app.lib.gsheets_cls import SS
from app.lib.dt import ddmmyyyy_to_date as to_date, dt_to_ddmmyyyy
from .donors import ytd_gifts
from .etapestry import call, get_udf
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def deliver(account, ss_gift, je_gifts):
    """Render and queue a donor receipt.
    @ss_gift: dict input from Bravo Sheets
    @je_gifts: list of eTapestry Gift objects
    """

    template = get_template(account, ss_gift)
    path = template['path']
    subject = template['subject']

    try:
        body = render_body(path, account, ss_gift=ss_gift, je_gifts=je_gifts)
    except Exception as e:
        log.exception('Failed to render receipt template')
        raise

    mid = mailgun.send(
        account['email'], subject, body, get_keys('mailgun'),
        v={'ss_row':ss_gift['ss_row'], 'group':g.group, 'type':'receipt'})

    return {'mid':mid, 'body':body, 'status':'QUEUED'}

#-------------------------------------------------------------------------------
def preview(acct_id=None, type_=None):

    paths = {
        "donation": "receipts/%s/collection_receipt.html" % g.group,
        "no_donation": "receipts/%s/no_collection.html" % g.group,
        "zero_donation": "receipts/%s/zero_collection.html" % g.group,
        "post_drop": "receipts/%s/dropoff_followup.html" % g.group,
        "cancelled": "receipts/%s/cancelled.html" % g.group
    }

    account = donors.get(acct_id or get_keys('admin')['pview_acct_id'])
    je_gifts = ytd_gifts(account['ref'], date.today().year)
    ss_gift = {
        'acct_id': account['id'],
        'date': date.today().strftime('%d/%m/%Y'),
        'amount':12.40,
        'next_pickup': get_udf('Next Pickup Date', account),
        'status':'Active',
        'ss_row':2
    }

    return render_body(
        paths[type_],
        account,
        ss_gift=ss_gift,
        je_gifts=je_gifts
    )

#-------------------------------------------------------------------------------
def get_template(acct, ss_gift):

    if not acct or not acct.get('ref'):
        raise Exception('Invalid account')

    if not acct.get('email'):
        log.debug('No account email')
        return {}

    gift_d = parse(ss_gift['date']).date()
    drop_d = parse(get_udf('Dropoff Date',acct)).date()
    nf = acct['nameFormat']

    if ss_gift['status'] == 'Cancelled':
        return {
            'path': "receipts/%s/cancelled.html" % g.group,
            'subject': "Your Account has been Cancelled"
        }
    elif drop_d and drop_d == gift_d:
        return {
            'path': "receipts/%s/dropoff_followup.html" % g.group,
            'subject': "Drop-off Complete"
        }
    elif ss_gift['amount'] == 0 and nf == 3:
        return {
            'path': "receipts/%s/zero_collection.html" % g.group,
            'subject': "See you next time"
        }
    elif ss_gift['amount'] == 0 and nf < 3:
        return {
            'path': "receipts/%s/no_collection.html" % g.group,
            'subject': "See you next time"
        }
    elif ss_gift['amount'] > 0:
        return {
            'path': "receipts/%s/collection_receipt.html" % g.group,
            'subject': "Thanks for your Donation"
        }
    else:
        raise Exception('Error determining receipt template.')

#-------------------------------------------------------------------------------
def render_body(path, acct, ss_gift=None, je_gifts=None):
    '''Convert all dates in data to long format strings, render into html'''

    history = []

    if je_gifts:
        for gift in je_gifts:
            history.append({
                'date':gift['gift']['date'].strftime('%B %-d, %Y'),
                'amount': gift['gift']['amount']
            })

    # Entry dates are in ISOFormat string. Convert to long format
    if ss_gift:
        ss_gift['date'] = parse(ss_gift['date']).strftime('%B %-d, %Y')

        if ss_gift.get('next_pickup'):
            npu = parse(ss_gift['next_pickup'])
            ss_gift['next_pickup'] = npu.strftime('%B %-d, %Y')

    try:
        body = render_template(
            path,
            to= acct['email'],
            account= acct,
            entry= ss_gift,
            history=history
        )
    except Exception as e:
        log.error('render receipt template: %s', str(e))
        return False

    return body

#-------------------------------------------------------------------------------
def on_delivered(group):
    '''Mailgun webhook called from view. Has request context'''

    g.group = group
    form = request.form
    keys = get_keys('google')
    log.debug('Receipt delivered to %s', form['recipient'])

    try:
        ss = SS(keys['oauth'], keys['ss_id'])
        wks = ss.wks('Donations')
        wks.updateCell(form['event'].upper(), row=form['ss_row'], col=3)
    except Exception as e:
        log.exception('Failed to update receipt status')
    finally:
        wks.service = None
        ss.service = None

#-------------------------------------------------------------------------------
def on_dropped(group):
    '''Mailgun webhook called from view. Has request context'''

    g.group = group
    form = request.form
    msg = 'Receipt to %s dropped. %s. %s' % (form['recipient'], form['reason'], form.get('description'))
    keys = get_keys('google')
    log.info(msg)

    try:
        ss = SS(keys['oauth'], keys['ss_id'])
        wks = ss.wks('Donations')
        wks.updateCell(form['event'].upper(), row=form['ss_row'], col=3)
    except Exception as e:
        log.exception('Failed to update receipt status')
    finally:
        ss.service = None
        wks.service = None

    from app.main.tasks import create_rfu
    create_rfu.delay(g.group, msg)


