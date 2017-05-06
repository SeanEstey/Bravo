'''app.main.signups'''
import json
from datetime import date, datetime
from flask import g, request, render_template
from app import get_keys
from app.lib import mailgun
from app.lib.gsheets import gauth, get_row, append_row, update_cell, to_range
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

    ss_id = get_keys('google')['ss_id']
    headers = get_row(service, ss_id, 'Signups', 1)
    row = []

    log.debug('headers=%s', headers)

    for field in headers:
        if form_data.has_key(field):
              row.append(form_data[field])
        else:
            row.append('')

    try:
        append_row(service, ss_id, 'Signups', row)
    except Exception, e:
        log.error('couldnt add signup="%s". desc="%s"',
            json.dumps(signup), str(e))
        log.debug(str(e))
        return 'There was an error handling your request'

    return 'success'

#-------------------------------------------------------------------------------
def send_welcome():
    '''Send a template email from Bravo Sheets
    @form: {'agency', 'recipient', 'type', 'tmpt_file', 'tmpt_vars, 'subject', 'from_row'}
    @form['type']: 'signup', 'receipt'
    Returns: mailgun ID
    '''
    #TODO: Change signature from Bravo Sheets

    #log.debug('/email/send: "%s"', args)

    args = request.get_json(force=True)
    to = args['recipient']
    g.group = args['agency']

    if args['type'] == 'signup':
        path = 'signups/%s/welcome.html' % g.group
    else:
        raise Exception('invalid template type')

    try:
        html = render_template(path, data=args['tmpt_vars'])
    except Exception as e:
        log.error('template error. desc=%s', str(e))
        log.debug('', exc_info=True)
        return str(e)

    try:
        mid = mailgun.send(to, args['subject'], html, get_keys('mailgun'), v={
            'agency':g.group, 'type':args['type'], 'from_row':args['from_row']})
    except Exception as e:
        log.error('could not email %s. desc=%s', to, str(e))
        create_rfu.delay(g.group, str(e))
        return str(e)

    log.debug('queued %s to %s', args.get('type'), to)

    return mid

#-------------------------------------------------------------------------------
def on_delivered(agcy):
    '''Mailgun webhook called from view. Has request context'''

    g.group = agcy
    log.info('signup welcome delivered to %s',
        request.form['recipient'])

    row = request.form['from_row']
    ss_id = get_keys('google')['ss_id']

    try:
        service = gauth(get_keys('google')['oauth'])
        headers = get_row(service, ss_id, 'Signups', 1)
        col = headers.index('Welcome')+1
        update_cell(service, ss_id, 'Signups', to_range(row,col), request.form['event'])
    except Exception as e:
        log.error('error updating sheet')

#-------------------------------------------------------------------------------
def on_dropped(agcy):
    g.group = agcy
    msg = 'signup welcome to %s dropped. %s.' %(
        request.form['recipient'], request.form['reason'])

    log.info(msg)

    row = request.form['from_row']
    ss_id = get_keys('google')['ss_id']

    try:
        service = gauth(get_keys('google')['oauth'])
        headers = get_row(service, ss_id, 'Signups', 1)
        col = headers.index('Welcome')+1
        update_cell(service, ss_id, 'Signups', to_range(row,col), request.form['event'])
    except Exception as e:
        log.error('error updating sheet')

    create_rfu.delay(g.group, msg + request.form.get('description'))

#-------------------------------------------------------------------------------
def lookup_carrier(phone):
    url = 'https://lookups.twilio.com/v1/PhoneNumbers/'
    '''
    headers = {
        "Authorization" : "Basic " + Utilities.base64Encode(this.twilio_auth_key)
    }

    try:
        response = UrlFetchApp.fetch(
            url+phone+'?Type=carrier', {
                'method':'GET',
                'muteHttpExceptions': True,
                'headers':headers
            }
        )
      }
    '''
