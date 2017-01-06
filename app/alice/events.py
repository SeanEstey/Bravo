'''app.alice.events'''

import logging
from app import etap, utils, db, bcolors
from flask import current_app, request, make_response, g
from datetime import datetime, date, time, timedelta
from app.booker import geo, search, book
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def do_support():
    account = getattr(g, 'account', None)

    rfu_task(
        agency['name'],
        'SMS help request: "%s"' % str(request.form['Body']),
        a_id = account['id'],
        name_addy = account['name']
    )

    return "Thank you. I'll have someone contact you as soon as possible. "

#-------------------------------------------------------------------------------
def reply_schedule():
    next_pu = etap.get_udf('Next Pickup Date', account)

    if not next_pu:
        return dialog['error']['acct_lookup']
    else:
        return 'Your next pickup is scheduled on ' +
                etap.ddmmyyyy_to_dt(next_pu).strftime('%A, %B %-d') + '.'

#-------------------------------------------------------------------------------
def add_driver_note():
    account = getattr(g, 'account', None)
    conf = getattr(g, 'agency_conf', None)

    etap.call(
        'modify_account',
        conf['etapestry'],
        data={
            'id': account['id'],
            'udf': {
                'Driver Notes': 'INSTRUCTION'
            },
            'persona': []
        })

    return "Thank you. I'll pass along your note to our driver. "

#-------------------------------------------------------------------------------
def skip_pickup():
    from app.notify import pus
    response = '' #pus.cancel_pickup()

    if response:
        return "I've taken you off the schedule. Thank you."
    else:
        return "I'm sorry, our driver has already been dispatched for the pickup."

#-------------------------------------------------------------------------------
def update_mobile():
    conf = getattr(g, 'agency_conf', None)

    rfu_task(
        conf['agency'],
        'SMS update account for following address '\
        'with mobile number:' + str(request.form['Body']),
        name_addy = request.form['From']
    )

    return \
        "Thank you. I'll have someone update your account for you "\
        "right away. "

#-------------------------------------------------------------------------------
def is_unsub():
    '''User has unsubscribed all messages from SMS number'''

    unsub_keywords = ['STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT']

    if request.form['Body'].upper() in unsub_keywords:
        logger.info('%s has unsubscribed from this sms number (%s)',
                    request.form['From'], request.form['To'])

        account = get_identity(make_response())
        agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

        rfu_task(
            agency['name'],
            'Contributor has replied "%s" and opted out of SMS '\
            'notifications.' % request.form['Body'],
            a_id = account['id'])

        return True

    return False

#-------------------------------------------------------------------------------
def pickup_request(msg, response):
    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    # Msg reply should contain address
    logger.info('pickup request address: \"%s\" (SMS: %s)', msg, request.form['From'])

    block = geo.find_block(agency['name'], msg, agency['google']['geocode']['api_key'])

    if not block:
        logger.error('could not find map for address %s', msg)

        send_reply('We could not locate your address', response)

        return False

    logger.info('address belongs to Block %s', block)

    set_cookie(response, 'status', None)

    r = search.search(agency['name'], block, radius=None, weeks=None)

    logger.info(r['results'][0])

    add_acct(
        msg,
        request.form['From'],
        r['results'][0]['name'],
        r['results'][0]['event']['start']['date']
    )

    #book.make(agency['name'], aid, block, date_str, driver_notes, name, email, confirmation):

    #gsheets.create_rfu(
    #  agency['name'],
    #  'Pickup request received (SMS: ' + from_ + ')',
    #  name_address = msg,
    #  date = datetime.datetime.now().strftime('%-m/%-d/%Y')
    #)

    return send_reply(
        "Thank you. We'll get back to you shortly with a pickup date",
        response
    )

#-------------------------------------------------------------------------------
def add_acct(address, phone, block, pu_date_str):
    conf = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    geo_result = geo.geocode(
        address,
        conf['google']['geocode']['api_key']
    )[0]

    #logger.info(utils.print_vars(geo_result, depth=2))

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

    logger.info(utils.print_vars(acct, depth=2))

    try:
        account = etap.call(
          'add_accounts',
          conf['etapestry'],
          [acct]
        )
    except Exception as e:
        logger.error("error calling eTap API: %s", str(e))
        raise EtapError('error calling eTap API')
