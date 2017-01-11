'''app.alice.events'''

import logging
from app import get_db, etap, utils, bcolors
from app.etap import EtapError
from flask import request, session
from datetime import datetime, date, time, timedelta
from app.booker import geo, search, book
from .dialog import dialog
from .helper import rfu_task
from app.notify.pus import cancel_pickup
log = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def request_support():
    account = session.get('account')

    rfu_task(
        session.get('conf')['name'],
        'SMS help request: "%s"' % str(request.form['Body']),
        a_id = account['id'],
        name_addy = account['name']
    )

    return dialog['support']['thanks']

#-------------------------------------------------------------------------------
def reply_schedule():
    next_pu = etap.get_udf('Next Pickup Date', session.get('account'))

    if not next_pu:
        return dialog['error']['internal']['lookup']
    else:
        return dialog['schedule']['next'] %(
            etap.ddmmyyyy_to_dt(next_pu).strftime('%A, %B %-d'))

#-------------------------------------------------------------------------------
def prompt_instructions():
    notific = get_latest_notific(request.form['From'])

    if not notific:
        return dialog['skip']['no_evnt']

    if event_begun(notific):
        return dialog['skip']['too_late']

    return dialog['instruct']['prompt']

#-------------------------------------------------------------------------------
def add_instruction():
    driver_notes = etap.get_udf('Driver Notes', session.get('account'))

    etap.call(
        'modify_account',
        session.get('conf')['etapestry'],
        data={
            'id': session.get('account')['id'],
            'udf': {
                'Driver Notes':\
                    '***%s***\n%s' %(
                    str(request.form['Body']), driver_notes)
            },
            'persona': []
        })

    return dialog['instruct']['thanks']



#-------------------------------------------------------------------------------
def skip_pickup():
    db = get_db()
    notific = get_latest_notific()
    acct = session.get('account')

    if not notific:
        msg = dialog['skip']['no_evnt']
        npu = etap.get_udf('Next Pickup Date', acct)

        if not npu:
            log.error('field udf->npu empty (etap_id=%s)', acct['id'])
            return msg

        return msg + dialog['schedule']['next'] %(
            etap.ddmmyyyy_to_local_dt(npu).strftime('%B %-d, %Y'))

    if event_begun(notific):
        return dialog['skip']['too_late']

    #log.debug(utils.formatter(notific, bson_to_json=True))

    result = cancel_pickup(notific['evnt_id'], notific['acct_id'])

    if not result:
        return dialog['error']['unknown']

    acct_doc = db.accounts.find_one({'_id':notific['acct_id']})

    future_pu_dt = utils.naive_utc_to_local(acct_doc['udf']['future_pickup_dt'])

    return \
        dialog['skip']['success'] + \
        dialog['schedule']['next'] % future_pu_dt.strftime('%B %-d, %Y')

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

    from phrases import unsubscribe

    db = get_db()

    if request.form['Body'].upper() in unsubscribe:
        log.info('%s has unsubscribed from this sms number (%s)',
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
def request_pickup(msg, response):
    db = get_db()

    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    # Msg reply should contain address
    log.info('pickup request address: \"%s\" (SMS: %s)', msg, request.form['From'])

    block = geo.find_block(agency['name'], msg, agency['google']['geocode']['api_key'])

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
    db = get_db()

    conf = db.agencies.find_one({'twilio.sms.number':request.form['To']})

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
        account = etap.call(
          'add_accounts',
          conf['etapestry'],
          [acct]
        )
    except Exception as e:
        log.error("error calling eTap API: %s", str(e))
        raise EtapError('error calling eTap API')
