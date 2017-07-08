'''app.main.signups'''
import json
from datetime import date, datetime
from flask import g, request, render_template
from app import get_keys
from app.lib import mailgun
from app.lib.gsheets import gauth, get_headers, update_cell, to_range
from app.main.etapestry import call, get_udf
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def add_etw_to_gsheets(signup):
    '''Called by emptiestowinn.com signup form only for now
    '''

    g.group = 'wsf'

    log.info('New signup received: %s %s',
      signup.get('first_name'),
      signup.get('last_name'))

    try:
        service = gauth(get_keys('google')['oauth'])
    except Exception as e:
        log.error('couldnt authenticate sheets. desc=%s', str(e))
        raise Exception('auth error. desc=%s' % str(e))

    form_data = {
        'Date': datetime.now().strftime('%-m/%-d/%Y'),
        'Office Notes': signup['special_requests'],
        'Address': signup['address'],
        'Postal': signup['postal'],
        'Landline': signup['phone'],
        'Email': signup['email'],
        'Receipt': signup['tax_receipt'],
        'Reason': signup['reason_joined'],
        'City': signup['city'],
        'Status': 'Dropoff'}

    if signup['account_type'] == 'Residential':
        form_data['First'] = signup['first_name']
        form_data['Last'] = signup['last_name']
        form_data['Name Format'] = 'Individual'
        form_data['Persona Type'] = 'Personal'
    elif signup['account_type'] == 'Business':
        form_data['Business'] = signup['account_name']
        form_data['Contact'] = signup['contact_person']
        form_data['Name Format'] = 'Business'
        form_data['Persona Type'] = 'Business'

    if 'title' in signup:
        form_data['Title'] = signup['title']

    if 'referrer' in signup:
        form_data['Referrer'] = signup['referrer']

    from app.lib.gsheets_cls import SS

    ss_id = get_keys('google')['ss_id']
    ss = SS(get_keys('google')['oauth'], get_keys('google')['ss_id'])
    wks = ss.wks('Signups')
    headers = wks.getRow(1)

    row = []

    for field in headers:
        if form_data.has_key(field):
              row.append(form_data[field])
        else:
            row.append('')

    try:
        wks.appendRows([row])
    except Exception, e:
        log.exception('couldnt add signup="%s". desc="%s"',
            json.dumps(signup), str(e))
        return 'There was an error handling your request'

    return 'success'

#-------------------------------------------------------------------------------
def check_duplicates(name=None, email=None, address=None, phone=None):
    '''Return list of acct_id of any duplicate accounts already in CRM DB'''

    fields = {}
    if name is not None:
        fields["name"] = name
    if email is not None:
        fields["email"] = email
    if address is not None:
        fields["address"] = address
    '''if phone is not None:
        fields["phone"] = {
            "type": "",
            "number": phone
        }
    '''

    return call(
        'check_duplicates',
        data=fields)

#-------------------------------------------------------------------------------
def send_welcome():
    '''Send a template email from Bravo Sheets
    @form: {'agency', 'recipient', 'type', 'tmpt_file', 'tmpt_vars, 'subject', 'from_row'}
    @form['type']: 'signup', 'receipt'
    Returns: mailgun ID
    '''

    from app.lib.dt import ddmmyyyy_to_date
    from app.main.etapestry import get_acct
    acct = get_acct(None, ref=request.form.get('ref'))

    udf = acct['accountDefinedValues']
    acct['accountDefinedValues'] = {
        'Dropoff Date': ddmmyyyy_to_date(get_udf('Dropoff Date', acct)),
        'Frequency': get_udf('Frequency', acct),
        'Status': get_udf('Status', acct),
        'Contact': get_udf('Contact', acct)
    }

    if not acct.get('email'):
        log.debug('Acct has no email to send Welcome')
        return 'No Email'

    try:
        html = render_template('signups/%s/welcome.html' % g.group,
            acct=acct, to=acct['email'])
    except Exception as e:
        log.exception('Email template error')
        raise

    row = int(float(request.form['row']))
    try:
        mid = mailgun.send(acct['email'], 'Welcome!', html, get_keys('mailgun'),
            v={'group':g.group, 'type':'signup', 'from_row':row})
    except Exception as e:
        from app.main.tasks import create_rfu
        log.exception('Failed to send Sign-up Welcome to %s', acct['email'],
            extra={'row':row})
        create_rfu.delay(g.group, str(e))
        raise

    log.debug('Queued welcome to %s', acct['email'])

    return mid

#-------------------------------------------------------------------------------
def on_delivered(group):
    '''Mailgun webhook called from view. Has request context'''

    g.group = group
    log.debug('Welcome delivered to %s', request.form['recipient'])
    row = request.form['from_row']
    ss_id = get_keys('google')['ss_id']

    try:
        service = gauth(get_keys('google')['oauth'])
        hdr = get_headers(service, ss_id, 'Signups')
        update_cell(service, ss_id, 'Signups',
            to_range(row, hdr.index('Welcome')+1),
            'SENT')
            #request.form['event'])
    except Exception as e:
        log.exception('Error updating Sheet')

#-------------------------------------------------------------------------------
def on_dropped(group):

    from app.api.manager import dump_headers
    g.group = group
    log.warning('Welcome dropped to %s', request.form['recipient'],
        extra={'headers':dump_headers(request.headers)})
    row = request.form['from_row']
    ss_id = get_keys('google')['ss_id']

    try:
        service = gauth(get_keys('google')['oauth'])
        hdr = get_headers(service, ss_id, 'Signups')
        update_cell(service, ss_id, 'Signups',
            to_range(row, hdr.index('Welcome')+1),
            'DROPPED')
            #request.form['event'])
    except Exception as e:
        log.exception('Error updating Sheet')

    from app.main.tasks import create_rfu
    create_rfu.delay(g.group,
        'Welcome dropped to %s. %s. %s.' %(
            request.form['recipient'],
            request.form['reason'],
            request.form.get('description')))
