'''app.main.signups'''
import json, logging
from datetime import date, datetime
from flask import g, request, current_app
from .. import gsheets, get_keys
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def add_gsheets(signup):
    '''Called by emptiestowinn.com signup form only for now
    '''

    log.info('New signup received: %s %s',
      signup.get('first_name'),
      signup.get('last_name'))

    try:
        service = gsheets.gauth(get_keys('google',agcy='wsf'))
    except Exception as e:
        log.error('couldnt authenticate sheets. desc=%s', str(e))
        raise Exception('auth error. desc=%s' % str(e))

    #wks = gc.open(current_app.config['GSHEET_NAME']).worksheet('Signups')

    form_data = {
        'Signup Date': datetime.now().strftime('%-m/%-d/%Y'),
        'Office Notes': signup['special_requests'],
        'Address': signup['address'],
        'Postal Code': signup['postal'],
        'Primary Phone': signup['phone'],
        'Email': signup['email'],
        'Tax Receipt': signup['tax_receipt'],
        'Reason Joined': signup['reason_joined'],
        'City': signup['city'],
        'Status': 'Dropoff'}

    if signup['account_type'] == 'Residential':
        form_data['First Name'] = signup['first_name']
        form_data['Last Name'] = signup['last_name']
        form_data['Name Format'] = 'Individual'
        form_data['Persona Type'] = 'Personal'
    elif signup['account_type'] == 'Business':
        form_data['Business Name'] = signup['account_name']
        form_data['Contact Person'] = signup['contact_person']
        form_data['Name Format'] = 'Business'
        form_data['Persona Type'] = 'Business'

    if 'title' in signup:
        form_data['Title'] = signup['title']

    if 'referrer' in signup:
        form_data['Referrer'] = signup['referrer']

    ss_id = get_keys('google',agcy='wsf')['ss_id']
    headers = gsheets.get_row(service, ss_id, 'Signups', 1)
    row = []

    for field in headers:
        if form_data.has_key(field):
              row.append(form_data[field])
    else:
        row.append('')

    try:
        gsheets.append_row(service, ss_id, 'Signups', row)
    except Exception, e:
        log.error('couldnt add signup="%s". desc="%s"', json.dumps(signup), str(e))
        log.debug('', exc_info=True)
        return 'There was an error handling your request'

    return 'success'

#-------------------------------------------------------------------------------
def on_email_delivered():
    '''Mailgun webhook called from view. Has request context'''

    log.info('signup welcome delivered to %s', request.form['recipient'])

    email = g.db.emails.find_one_and_update(
        {'mid': request.form['Message-Id']},
        {'$set': {'status': request.form['event']}})


    log.error('update cell not implemented yet')

    #gsheets.update_cell(service, ss_id, range_, value)

    #gsheets.update_entry(
    #  email['agency'],
    #  request.form['event'],
    #  email['on_status']['update'])

#-------------------------------------------------------------------------------
def on_email_dropped():
    msg = 'signup welcome to %s dropped. %s.' %(
        request.form['recipient'], request.form['reason'])

    log.info(msg)

    email = g.db.emails.find_one_and_update(
        {'mid': request.form['Message-Id']},
        {'$set': {'status': request.form['event']}})

    log.error('update cell not implemented yet')

    #gsheets.update_entry(
    #  email['agency'],
    #  request.form['event'],
    #  email['on_status']['update'])

    create_rfu.delay(
        email['agency'], msg + request.form.get('description'),
        options={
            'Date': date.today().strftime('%-m/%-d/%Y')})

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
