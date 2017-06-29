'''app.alice.events'''
from flask import g, request, session
from datetime import datetime, date, time, timedelta
from app.lib.dt import to_local, ddmmyyyy_to_dt
from app.lib.utils import obj_vars
from app.main.etap import call, get_udf, EtapError
from app.booker import geo, search, book
from .dialog import dialog
from .util import related_notific, event_begun, set_notific_reply
from app.main.tasks import create_rfu
from app.notify.tasks import skip_pickup as skip_pickup_task
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def request_support():
    acct = session.get('account')

    create_rfu.delay(
        session.get('agcy'),
        'SMS help request: "%s"\n%s' %(
            str(request.form['Body']),
            session.get('from')),
        options={
            'ID': acct['id'],
            'Account': acct['name']})

    return dialog['support']['thanks']

#-------------------------------------------------------------------------------
def reply_schedule():
    next_pu = get_udf('Next Pickup Date', session.get('account'))

    if not next_pu:
        return dialog['error']['internal']['lookup']
    else:
        return dialog['schedule']['next'] %(
            ddmmyyyy_to_dt(next_pu).strftime('%A, %B %-d'))

#-------------------------------------------------------------------------------
def prompt_instructions():
    if not session.get('notific_id'):
        return dialog['skip']['no_evnt']

    #log.debug('is_notific_reply=%s', session.get('valid_notific_reply'))

    if session.get('valid_notific_reply') == False:
        return dialog['skip']['too_late']

    # Did user include instruction details along w/ INSTRUCTION keyword?
    # Otherwise, if only INSTRUCTIONS keyword provided, prompt user for details

    msg = str(request.form['Body'].encode('ascii', 'ignore')).strip()
    words = msg.split(' ')

    if len(words) > 1:
        session['on_complete'] = None
        return add_instructions()
    else:
        return dialog['instruct']['prompt']

#-------------------------------------------------------------------------------
def add_instructions():
    # We've already verified user reply is valid for a notific event
    set_notific_reply()

    instruct = request.form['Body']
    acct = session.get('account')
    old_notes = get_udf('Driver Notes', acct)

    call('modify_acct',
        data={
          'acct_id': acct['id'],
          'udf': {'Driver Notes': '***%s***\n%s' %(str(instruct), old_notes)},
          'persona': []
        }
    )

    return dialog['instruct']['thanks']

#-------------------------------------------------------------------------------
def skip_pickup():
    acct = session.get('account')

    if not session.get('notific_id'):
        msg = dialog['skip']['no_evnt']
        npu = get_udf('Next Pickup Date', acct)

        if not npu:
            log.error('field udf->npu empty (etap_id=%s)', acct['id'])
            return msg

        return msg + dialog['schedule']['next'] %(
            to_local(dt=ddmmyyyy_to_dt(npu)).strftime('%B %-d, %Y'))

    if session.get('valid_notific_reply') == False:
        return dialog['skip']['too_late']

    notific = g.db.notifics.find_one({'_id':session.get('notific_id')})

    try:
        result = skip_pickup_task.delay(
            evnt_id=str(notific['evnt_id']),
            acct_id=str(notific['acct_id']))
    except Exception as e:
        log.error('skip_pickup failed')
        log.debug(str(e))
        return dialog['error']['unknown']

    dt = g.db.accounts.find_one(
        {'_id':notific['acct_id']}
    )['udf']['future_pickup_dt']

    return \
        dialog['skip']['success'] + \
        dialog['schedule']['next'] % (to_local(dt=dt).strftime('%B %-d, %Y'))

#-------------------------------------------------------------------------------
def update_mobile():
    create_rfu.delay(
        session.get('agcy'),
        'SMS update account for following address '\
        'with mobile number:' + str(request.form['Body']),
        options = {
            'Account': request.form['From']})

    return \
        "Thank you. I'll have someone update your account for you "\
        "right away. "

#-------------------------------------------------------------------------------
def is_unsub():
    '''User has unsubscribed all messages from SMS number'''

    from phrases import unsubscribe

    if request.form['Body'].upper() in unsubscribe:
        log.info(
            '%s has unsubscribed from this sms number (%s)',
            request.form['From'], request.form['To'])

        # FIXME
        #account = get_identity(make_response())
        #agency = g.db['groups'].find_one({
        #    'twilio.sms.number':request.form['To']})

        create_rfu.delay(
            session.get('agcy'),
            'Contributor has replied "%s" and opted out of SMS '\
            'notifications.' % request.form['Body'],
            options = {'ID': account['id']})
        return True

    return False

#-------------------------------------------------------------------------------
def request_pickup():

    address = request.form['Body']
    g.group = session.get('agcy')
    conf = session.get('conf')

    # Msg reply should contain address
    log.info('pickup request at \"%s\" (SMS: %s)', address, request.form['From'])

    block = geo.find_block(g.group, address, conf['google']['geocode']['api_key'])

    if not block:
        log.error('could not find map for address %s', address)
        create_rfu.delay(
            g.group,
            "Could not locate block for address \"%s\"" % address,
            options={
                "Account": "Mobile: %s" % request.form['From']})
        return dialog['anon']['geo_fail']

    log.info('address belongs to Block %s', block)

    #set_cookie(response, 'status', None)

    r = search.search(block, radius=None, weeks=None, agcy=g.group)

    #log.info(r['results'][0])

    #add_acct(
    #    address,
    #    request.form['From'],
    #    r['results'][0]['name'],
    #    r['results'][0]['event']['start']['date'])

    #book.make(agcy, aid, block, date_str, driver_notes, name, email, confirmation):
    from json import dumps

    create_rfu.delay(
        g.group,
        "Pickup request result: %s" % dumps(r['results']),
        options={
            "Account": "Address: %s\nMobile: %s" %(address, request.form['From'])})

    return dialog['anon']['geo_success']

#-------------------------------------------------------------------------------
def add_acct(address, phone, block, pu_date_str):
    conf = session.get('conf')

    geo_result = geo.geocode(
        address,
        conf['google']['geocode']['api_key']
    )[0]

    #log.info(utils.obj_vars(geo_result, depth=2))

    addy = {
        'postal': None,
        'city': None,
        'route': None,
        'street': None
    }

    for component in geo_result['address_components']:
        if 'postal_code' in component['types']:
            addy['postal'] = component['short_name']
        elif 'street_number' in component['types']:
            addy['street'] = component['short_name']
        elif 'locality' in component['types']:
            addy['city'] = component['short_name']
        elif 'route' in component['types']:
            addy['route'] = component['short_name']

    parts = pu_date_str.split('-')
    ddmmyyyy_pu = '%s/%s/%s' %(parts[2], parts[1], parts[0])

    acct = {
        'udf': {
            'Status': 'One-time',
            'Signup Date': datetime.today().strftime('%d/%m/%Y'),
            'Next Pickup Date': ddmmyyyy_pu.encode('ascii', 'ignore'),
            'Block': block.encode('ascii', 'ignore'),
            #'Driver Notes': signup[this.headers.indexOf('Driver Notes')],
            #'Office Notes': signup[this.headers.indexOf('Office Notes')],
            'Tax Receipt': 'Yes',
            #'SMS' "+1" + phone.replace(/\-|\(|\)|\s/g, "")
         },
         'persona': {
            'personaType': 'Personal',
            'address': (addy['street'] + ' ' + addy['route']).encode('ascii','ignore'),
            'city': addy['city'].encode('ascii', 'ignore'),
            'state': 'AB',
            'country': 'CA',
            'postalCode': addy['postal'].encode('ascii', 'ignore'),
            'phones': [
                {'type': 'Mobile', 'number': phone}
            ],
			'nameFormat': 1,
			'name': 'Unknown Unknown',
			'sortName': 'Unknown, Unknown',
			'firstName': 'Unknown',
			'lastName': 'Unknown'
        }
    }

    log.info(obj_vars(acct, depth=2))

    try:
        call('add_accts', data=[acct])
    except Exception as e:
        log.exception('Error creating account.')
        raise EtapError('error calling eTap API')
