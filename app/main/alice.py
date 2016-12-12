'''app.alice'''

import logging
import twilio
from twilio import twiml
from datetime import datetime, date, time, timedelta
import re
import os
import json
from twilio.rest.lookups import TwilioLookupsClient
from flask import current_app, request, make_response

from .. import etap, utils, gsheets, schedule

from app import db, bcolors
from app.booker import geo, search, book

logger = logging.getLogger(__name__)


class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def is_unsub():
    '''User has unsubscribed all messages from SMS number'''

    unsub_keywords = ['STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT']

    if request.form['Body'].upper() in unsub_keywords:
        logger.info('%s has unsubscribed from this sms number (%s)',
                    request.form['From'], request.form['To'])

        account = get_identity(make_response())
        agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

        from .. import tasks
        tasks.rfu.apply_async(
            args=[
                agency['name'],
                'Contributor has replied "%s" and opted out of SMS '\
                'notifications.' % request.form['Body']
            ],
            kwargs={
                'a_id':account['id'],
                '_date': date.today().strftime('%-m/%-d/%Y')
            },
            queue=current_app.config['DB']
        )
        return True

    return False

#-------------------------------------------------------------------------------
def on_receive():
    '''Received an incoming SMS message.
    Either initiating a keyword request or replying to conversation.
    Keywords: SCHEDULE, PICKUP
    '''

    logger.debug(request.cookies)
    msg = request.form['Body']
    logger.info('To Alice: %s"%s"%s', bcolors.BOLD, msg, bcolors.ENDC)

    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    from_ = request.form['From']
    response = make_response()
    account = None
    greeting = ''

    set_cookie(response, 'messagecount', int(request.cookies.get('messagecount', 0))+1)

    account = get_identity(response)

    if not account:
        return handle_stranger(response)

    # Are we waiting for response from known user?
    if request.cookies.get('status') == 'add_to_schedule_confirm':
        if 'YES' in msg.upper():
            set_cookie(response, 'status', 'completed')

            return send_reply(
                'Thank you. I\ll forward your request to customer service.', response)
        else:
            return send_reply(
                get_help_reply(response, account=account),
                response)
    elif request.cookies.get('status') == 'get_address':
        return pickup_request(msg, response)

    # Keyword handler
    if 'SCHEDULE' in msg.upper():
        if not etap.get_udf('Next Pickup Date', account):
            logger.error(
                'missing Next Pickup Date for account %s (SMS: %s)',
                account['id'], from_)

            return send_reply(
                "You are not currently scheduled for pickups. Would you like to be?",
                response)

            set_cookie(response, 'status', 'add_to_schedule_confirm')

        npu_dt = etap.ddmmyyyy_to_dt(etap.get_udf('Next Pickup Date', account))
        npu_str = npu_dt.strftime('%A, %B %-d')

        return send_reply(
            'Your next pickup is scheduled on ' + npu_str + '.',
            response
        )
    elif 'PICKUP' in msg.upper():
        logger.info('new pickup request (SMS: %s)', from_)

        set_cookie(response, 'status', 'get_address')

        return send_reply(
            'Ok, I can book a pickup for you. What\'s your address?',
            response
        )
    # No keyword.
    else:
        return send_reply(
            get_help_reply(response, account=account),
            response
        )

#-------------------------------------------------------------------------------
def handle_stranger(response):
    if request.cookies.get('status') == 'prompt_address':
        from .. import tasks
        tasks.rfu.apply_async(args=[
            agency['name'],
            'Account at address ' + request.form['Body']+ ' requests '\
            'to add mobile number ' + from_],
            queue=current_app.config['DB'])

        set_cookie(response, 'status', 'address_received')

        return send_reply('Thank you. We\'ll update your account.', response)

    else:
        set_cookie(response, 'status', 'prompt_address')

        return send_reply(
            "I'm sorry, I don't recognize this phone number. Do you have an "\
            "account? If you let me know your address I can register this "\
            "number for you.",
            response
        )

#-------------------------------------------------------------------------------
def get_name(account):
    name = None

    if account['nameFormat'] == 1: # individual
        name = account['firstName']

        # for some reason firstName is sometimes empty even if populated in etap
        if not name:
            name = account['name']
    else:
        name = account['name']

    return name

#-------------------------------------------------------------------------------
def set_cookie(response, k, v):
    expires=datetime.utcnow() + timedelta(hours=4)
    response.set_cookie(
        k,
        value=str(v),
        expires=expires.strftime('%a,%d %b %Y %H:%M:%S GMT'))

#-------------------------------------------------------------------------------
def new_conversation():
    if int(request.cookies.get('messagecount', 0)) == 0:
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def get_greeting(account=None):
    '''A simple hello at the beginning of a conversation'''

    return 'Good ' + get_tod() + ' '

#-------------------------------------------------------------------------------
def get_help_reply(response, account=None):
    reply = ''

    messagecount = int(request.cookies.get('messagecount', 0))

    if messagecount == 0:
        reply += 'How can I help you today? '

    reply += 'If you reply with the word "schedule" I can give you your '\
             'next pickup date.'

    return reply

#-------------------------------------------------------------------------------
def send_reply(msg, response):

    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    if agency['name'] == 'vec':
        ASSISTANT_NAME = 'Alice'
        reply = ASSISTANT_NAME + ': '
    else:
        reply = ''

    account = get_identity(response)

    if new_conversation():
        reply += get_greeting(account)

        if account:
            reply += ', ' + get_name(account) + '. '
        else:
            reply += '. '
    else:
        if account:
            reply += get_name(account) + ', '
            msg = msg[0].lower() + msg[1:]

    twml = twiml.Response()

    reply += msg

    twml.message(reply)

    logger.info('%s"%s"%s', bcolors.BOLD, reply, bcolors.ENDC)

    response.data = str(twml)
    return response

#-------------------------------------------------------------------------------
def get_tod():
    hour = datetime.now().time().hour

    if hour < 12:
        return 'morning'
    elif hour >= 12 and hour < 18:
        return 'afternoon'
    elif hour >= 18:
        return 'evening'

#-------------------------------------------------------------------------------
def get_identity(response):
    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    if request.cookies.get('etap_id'):
        return etap.call(
          'get_account',
          agency['etapestry'],
          {'account_number':request.cookies['etap_id']},
          silence_exceptions=True
        )

    # New conversation. Try to identify phone number
    try:
        account = etap.call(
          'find_account_by_phone',
          agency['etapestry'],
          {"phone": request.form['From']}
        )
    except Exception as e:
        logger.error("error calling eTap API: %s", str(e))
        raise EtapError('error calling eTap API')

    if not account:
        logger.info(
            'no matching etapestry account found (SMS: %s)',
            request.form['From'])



        from .. import tasks
        tasks.rfu.apply_async(args=[
            agency['name'],
            'Received text mobile number %s not matching eTapestry account' %
            request.form['Body']],
            queue=current_app.config['DB'])

        return False

    logger.debug(account)

    name = get_name(account)

    expires=datetime.utcnow() + timedelta(hours=4)

    set_cookie(response, 'etap_id', account['id'])
    set_cookie(response, 'name', name)
    set_cookie(response, 'agency', agency['name'])

    return account

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
