'''app.alice.events'''
import logging
from app import get_logger, etap, utils
from app.dt import to_local, ddmmyyyy_to_dt
from app.etap import EtapError
from flask import g, request, session
from datetime import datetime, date, time, timedelta
from app.booker import geo, search, book
from .dialog import dialog
from .util import related_notific, event_begun, set_notific_reply
from app.main.tasks import create_rfu
from app.notify.tasks import skip_pickup as skip_pickup_task
log = get_logger('alice.events')

#-------------------------------------------------------------------------------
def request_support():
    acct = session.get('account')

    create_rfu.delay(
        g.user.agency,
        'SMS help request: "%s"' % str(request.form['Body']),
        options={
            'Account Number': acct['id'],
            'Name & Address': acct['name']})

    return dialog['support']['thanks']

#-------------------------------------------------------------------------------
def reply_schedule():
    next_pu = etap.get_udf('Next Pickup Date', session.get('account'))

    if not next_pu:
        return dialog['error']['internal']['lookup']
    else:
        return dialog['schedule']['next'] %(
            ddmmyyyy_to_dt(next_pu).strftime('%A, %B %-d'))

#-------------------------------------------------------------------------------
def prompt_instructions():
    if not session.get('notific_id'):
        return dialog['skip']['no_evnt']

    log.debug('valid_notific_reply=%s', session.get('valid_notific_reply'))

    if session.get('valid_notific_reply') == False:
        return dialog['skip']['too_late']

    return dialog['instruct']['prompt']

#-------------------------------------------------------------------------------
def add_instructions():
    # We've already verified user reply is valid for a notific event
    set_notific_reply()

    instruction = request.form['Body']
    acct = session.get('account')
    driver_notes = etap.get_udf('Driver Notes', acct)

    etap.call(
        'modify_acct',
        session.get('conf')['etapestry'],
        data={
            'acct_id': acct['id'],
            'udf': {
                'Driver Notes':\
                    '***%s***\n%s' %(
                    str(instruction), driver_notes)
            },
            'persona': []
        })

    return dialog['instruct']['thanks']

#-------------------------------------------------------------------------------
def skip_pickup():
    acct = session.get('account')

    if not session.get('notific_id'):
        msg = dialog['skip']['no_evnt']
        npu = etap.get_udf('Next Pickup Date', acct)

        if not npu:
            log.error('field udf->npu empty (etap_id=%s)', acct['id'])
            return msg

        return msg + dialog['schedule']['next'] %(
            to_local(dt=ddmmyyyy_to_dt(npu)).strftime('%B %-d, %Y'))

    if session.get('valid_notific_reply') == False:
        return dialog['skip']['too_late']

    notific = g.db.notifics.find_one({'_id':session.get('notific_id')})

    #log.debug(utils.formatter(notific, bson_to_json=True))

    try:
        result = skip_pickup_task(
            evnt_id=str(notific['evnt_id']),
            acct_id=str(notific['acct_id']))
    except Exception as e:
        log.error('skip_pickup failed')
        log.debug('',exc_info=True)
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
        g.user.agency,
        'SMS update account for following address '\
        'with mobile number:' + str(request.form['Body']),
        options = {
            'Name & Address': request.form['From']})

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

        #agency = g.db.agencies.find_one({
        #    'twilio.sms.number':request.form['To']})

        create_rfu.delay(
            g.user.agency,
            'Contributor has replied "%s" and opted out of SMS '\
            'notifications.' % request.form['Body'],
            options = {
                'Account Number': account['id']})

        return True

    return False

#-------------------------------------------------------------------------------
def request_pickup(msg, response):
    agency = session.get('agency')
    conf = sessin.get('conf')

    # Msg reply should contain address
    log.info('pickup request address: \"%s\" (SMS: %s)', msg, request.form['From'])

    block = geo.find_block(agency, msg, conf['google']['geocode']['api_key'])

    if not block:
        log.error('could not find map for address %s', msg)

        send_reply('We could not locate your address', response)

        return False

    log.info('address belongs to Block %s', block)

    set_cookie(response, 'status', None)

    r = search.search(agency['name'], block, radius=None, weeks=None)

    log.info(r['results'][0])

    add_acct(
        msg,
        request.form['From'],
        r['results'][0]['name'],
        r['results'][0]['event']['start']['date']
    )

    #book.make(agency['name'], aid, block, date_str, driver_notes, name, email, confirmation):

    return send_reply(
        "Thank you. We'll get back to you shortly with a pickup date",
        response
    )

#-------------------------------------------------------------------------------
def add_acct(address, phone, block, pu_date_str):
    conf = session.get('conf')

    geo_result = geo.geocode(
        address,
        conf['google']['geocode']['api_key']
    )[0]

    #log.info(utils.print_vars(geo_result, depth=2))

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

    log.info(utils.print_vars(acct, depth=2))

    try:
        etap.call(
          'add_accts',
          conf['etapestry'],
          [acct]
        )
    except Exception as e:
        log.error("error calling eTap API: %s", str(e))
        raise EtapError('error calling eTap API')
