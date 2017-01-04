'''app.main.alice'''

import logging
import string
import twilio
from twilio import twiml
from datetime import datetime, date, time, timedelta
import re
import os
import json
from twilio.rest.lookups import TwilioLookupsClient
from flask import current_app, request, make_response, g

from .. import etap, utils, gsheets
from app import db, bcolors
from app.booker import geo, search, book

logger = logging.getLogger(__name__)

class EtapError(Exception):
    pass

REQ_KEYWORDS = ['NOPICKUP', 'NO PICKUP', 'PICKUP', 'SCHEDULE', 'SUPPORT', 'INSTRUCTION']
GEN_KEYWORDS = ['THANKS', 'THANK YOU', 'THX']

# Fixed Replies

REPL_INTRO = \
    "How can I help you?"
REPL_DEFAULT = \
    "Ask me about your SCHEDULE for your next pickup date, or request live SUPPORT."
REPL_ETAP_ERR = \
    "I'm sorry, there seems to be a problem looking up "\
    "your account. We'll look into the matter for you."
REPL_DRIVER_DISPATCHED = \
    "I'm sorry, our driver has already been dispatched for the pickup."
SUPPORT_KW_REPL = \
    "Tell me what you need help with and I'll forward your request to the right person."
INSTRUCTION_RECEIVED = \
    "Thank you. I'll pass along your note to our driver. "
SUPPORT_RECEIVED = \
    "Thank you. I'll have someone contact you as soon as possible. "\
STRANGER = \
    "I'm sorry, I don't recognize this phone number. Do you have an "\
    "account? If you let me know your address I can register this "\
    "number for you."


#-------------------------------------------------------------------------------
def on_receive():
     '''Received an incoming SMS message.
    Cookies used that persist beyond each request: 'etap_id', 'status', 'messagecount'
    Per request flask.g variables: 'acct_name' '''

    msg = str(request.form['Body']).strip() # Unicode causes parsing issues
    from_ = request.form['From']
    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    log_msg()
    msg_count = increment_msg_count()
    response = make_response()

    try:
        account = get_identity(response)
    except Exception as e:
        return send_reply(REPL_ETAP_ERR, response)
    else:
        save_msg(agency['name'], from_, msg, account=account)

        if not account:
            return handle_stranger(response)

    if msg_count == 1:
        return new_conversation_reply(response, account)

    # In a conversation. either AWAITING_KEYWORD or AWAITING_REPLY
    # AWAITING_KEYWORD: expecting 1 or more possible keywords
    # AWAITING_REPLY: awaiting reply to previous keyword

    if awaiting_reply():
        return handle_reply(response, msg, account)
    elif awaiting_keyword():
        if has_keyword(msg):
            return handle_keyword(response, msg, account)

    # Not expecting a reply
    if conversation_ended(msg):
        return send_reply("You're welcome!", response)

    # TODO: Some other unprompted keyword?
    # Can't understand request. Send default reply.
    # TODO: If 3rd time sending default reply, offer assistance

    return send_reply(
        get_default_reply(response, account=account),
        response
    )

#-------------------------------------------------------------------------------
def new_conversation_reply(response, account):
    # Look for any keywords
    if find_keyword(msg, REQ_KEYWORDS):
        return handle_keyword(response, msg, account)
    else:
        # prompt default msg
        return send_reply(
            get_default_reply(response, account=account),
            response
        )

#-------------------------------------------------------------------------------
def find_keyword(msg, key_list):
    '''@msg: should be casted to string and stripped()'''

    cleaned_msg = msg.upper().translate(None, string.punctuation)
    parts = cleaned_msg.split(' ')

    # Keyword command issued?
    for part in parts:
        if part in key_list:
            return True

    return False

#-------------------------------------------------------------------------------
def conversation_ended(msg):
    # TODO: can't be first message in conversation
    # TODO: check messagecount > 2

    return find_keyword(msg, GEN_KEYWORDS)

#-------------------------------------------------------------------------------
def get_identity(response):
    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    if request.cookies.get('etap_id'):
        account = etap.call(
          'get_account',
          agency['etapestry'],
          {'account_number':request.cookies['etap_id']},
          silence_exceptions=True
        )
        g.acct_name = get_name(account)
        return account

    # New conversation. Try to identify phone number
    try:
        account = etap.call(
          'find_account_by_phone',
          agency['etapestry'],
          {"phone": request.form['From']}
        )
    except Exception as e:
        rfu_task(
            agency['name'],
            'SMS eTap error: "%s"' % str(e),
            name_addy = request.form['From']
        )

        logger.error("eTapestry API: %s", str(e))
        raise EtapError('eTapestry API: %s' % str(e))

    if not account:
        logger.info(
            'no matching etapestry account found (SMS: %s)',
            request.form['From'])

        #rfu_task(
        #    agency['name'],
        #    'No eTapestry account linked to this mobile number. '\
        #    '\nMessage: "%s"' % request.form['Body'],
        #    name_addy='Mobile: %s' % request.form['From'])

        return False

    expires=datetime.utcnow() + timedelta(hours=4)

    g.acct_name = get_name(account)
    logger.debug('set g.acct_name: %s', getattr(g, 'acct_name', None))

    set_cookie(response, 'etap_id', account['id'])

    return account

#-------------------------------------------------------------------------------
def awaiting_answer():
    return get_cookie('AWAITING_ANSWER')

#-------------------------------------------------------------------------------
def is_command():
    msg = str(request.form['Body']).strip()
    cleaned_msg = msg.upper().translate(None, string.punctuation)
    parts = cleaned_msg.split(' ')

    # Keyword command issued?
    for part in parts:
        if part in REQ_KEYWORDS:
            return part

    return False

#-------------------------------------------------------------------------------
def handle_command(msg, from_, account, response):
    # Keyword handler
    if msg.upper() in ['NOPICKUP', 'NO PICKUP']:
        return send_reply(REPL_DRIVER_DISPATCHED, response)
    elif 'SCHEDULE' in msg.upper():
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
    elif 'SUPPORT' in msg.upper():
        set_cookie(response, 'status', 'get_help_request')

        return send_reply(REPL_SUPPORT_REQ, response)
    elif 'PICKUP' in msg.upper():
        logger.info('new pickup request (SMS: %s)', from_)

        set_cookie(response, 'status', 'get_address')

        return send_reply(
            'Ok, I can book a pickup for you. What\'s your address?',
            response
        )

#-------------------------------------------------------------------------------
def handle_answer(response, account):
    '''User was asked a question. Process their answer'''

    awaiting = get_cookie('AWAITING_ANSWER')
    set_cookie(response, 'AWAITING_ANSWER', False)

    if awaiting == 'INSTRUCTION':
        # TODO: update eTap acct Driver Notes

        return send_reply(REPL_INSTRUCTION_RECEIVED, response)
    elif awaiting == 'SUPPORT':
        rfu_task(
            agency['name'],
            'SMS help request: "%s"' % msg,
            a_id = account['id'],
            name_addy = account['name']
        )

        return send_reply(
            SUPPORT_RECEIVED + 'Enjoy your %s' % get_tod(),
            response)
    if awaiting == 'BOOKME':
        if 'YES' in msg.upper():
            return send_reply(
                "Thank you. I'll forward your request.", response)
        else:
            return send_reply(
                get_default_reply(response, account=account),
                response
            )
    elif awaiting == 'ADDRESS':
        return pickup_request(msg, response)

#-------------------------------------------------------------------------------
def log_msg():
    logger.debug(request.form.to_dict())

    logger.info('To Alice: %s"%s"%s (%s)',
                bcolors.BOLD, msg, bcolors.ENDC, request.form['From'])

#-------------------------------------------------------------------------------
def save_msg(agency, from_, msg, account=None):
    date_str = date.today().isoformat()

    if not db.alice.find_one({'from':from_,'date':date_str}):
        db.alice.insert_one({
            'agency': agency,
            'account': account,
            'twilio': [request.form.to_dict()],
            'from':from_,
            'date':date.today().isoformat(),
            'last_msg_dt': utils.naive_to_local(datetime.now()),
            'messages':[msg]})
    else:
        db.alice.update_one(
            {'from':from_, 'date': date_str},
            {'$set': {'last_msg_dt': utils.naive_to_local(datetime.now())},
             '$push': {'messages': msg, 'twilio': request.form.to_dict()}})

#-------------------------------------------------------------------------------
def handle_stranger(response):
    if request.cookies.get('status') == 'prompt_address':
        rfu_task(
            'vec',
            'Donor at address provided requested '\
            'to register mobile number with their account: %s' % request.form['From'],
            name_addy=request.form['Body'])

        set_cookie(response, 'status', 'address_received')

        return send_reply('Thank you. We\'ll update your account.', response)

    else:
        set_cookie(response, 'status', 'prompt_address')

        return send_reply(STRANGER, response)

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
def get_cookie(key):
    return request.cookies.get(key)

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
def get_greeting():
    '''A simple hello at the beginning of a conversation'''

    return 'Good ' + get_tod() + ' '

#-------------------------------------------------------------------------------
def get_default_reply(response, account=None):
    reply = ''

    messagecount = int(request.cookies.get('messagecount', 0))

    if messagecount == 0:
        reply += REPL_INTRO

    reply += REPL_DEFAULT

    return reply

#-------------------------------------------------------------------------------
def send_reply(msg, response):

    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    if agency['name'] == 'vec':
        ASSISTANT_NAME = 'Alice'
        reply = ASSISTANT_NAME + ': '
    else:
        reply = ''

    name = getattr(g, 'acct_name', None)
    logger.debug('acct name: %s', name)

    if new_conversation():
        reply += get_greeting()

        if name:
            reply += ', ' + name + '. '
        else:
            reply += '. '
    else:
        if name:
            reply += name + ', '
            msg = msg[0].lower() + msg[1:]

    twml = twiml.Response()

    reply += msg

    twml.message(reply)

    logger.info('%s"%s"%s', bcolors.BOLD, reply, bcolors.ENDC)

    response.data = str(twml)

    db.alice.update_one(
        {'from':request.form['From'], 'date': date.today().isoformat()},
        {'$push': {'messages':reply}})

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
def get_chatlogs(agency, start_dt=None):
    if not start_dt:
        start_dt = datetime.utcnow() - timedelta(days=14)

    # double-check start_dt arg is UTC

    chats = db.alice.find(
        {'agency':agency, 'last_msg_dt': {'$gt': start_dt}},
        {'agency':0, '_id':0, 'date':0, 'account':0, 'twilio':0}
    ).sort('last_msg_dt',-1)

    chats = list(chats)
    for chat in chats:
        chat['Date'] =  utils.tz_utc_to_local(
            chat.pop('last_msg_dt')
        ).strftime('%b %-d @ %-I:%M%p')
        chat['From'] = chat.pop('from')
        chat['Messages'] = chat.pop('messages')

    return chats

#-------------------------------------------------------------------------------
def clear_cookies(response):
    response.set_cookie('name', expires=0)
    response.set_cookie('status', expires=0)
    response.set_cookie('etap_id', expires=0)
    response.set_cookie('agency', expires=0)
    response.set_cookie('messagecount', expires=0)
    return response

#-------------------------------------------------------------------------------
def increment_msg_count(response):
    count = int(get_cookie('messagecount') or 0) + 1
    set_cookie(response, 'messagecount', count)
    return count

#-------------------------------------------------------------------------------
def rfu_task(agency, note,
             a_id=None, npu=None, block=None, name_addy=None):

    from .. import tasks
    tasks.rfu.apply_async(
        args=[
            agency,
            note
        ],
        kwargs={
            'a_id': a_id,
            'npu': npu,
            'block': block,
            '_date': date.today().strftime('%-m/%-d/%Y'),
            'name_addy': name_addy
        },
        queue=current_app.config['DB'])
