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

# Global s

KEYWORDS = [
    'INSTRUCTION',
    'REGISTER',
    'SCHEDULE',
    'SKIP',
    'SUPPORT',
    'UPDATE'
]

CONVERSATION_ENDINGS = [
    'THANKS',
    'THANK YOU',
    'THX',
    'SOUNDS GOOD',
    'OK'
]

dialog = {
    "general": {
        "intro": \
            "How can I help you?",
        "thanks_reply": \
            "You're welcome!"
    },
    "user": {
        "options": \
            "You can guide me with keywords. "\
            "Ask me about your pickup SCHEDULE, or request live SUPPORT.",
    },
    "unregistered": {
        "options": \
            "I don't recognize this number. "\
            "Do you have an account? I can UPDATE it for you. "\
            "If you're new, you can REGISTER for a pickup. "
    },
    "k": {
        "SKIP": {
            "expired": \
                "I'm sorry, our driver has already been dispatched for the pickup."
        },
        "SUPPORT": {
            "prompt": \
                "Tell me what you need help with and I'll forward your "\
                "request to the right person.",
            "received": \
                "Thank you. I'll have someone contact you as soon as possible. "\
        },
        "INSTRUCTION": {
            "prompt": \
                "Tell me what you'd like instructions to pass along to our driver",
            "received": \
                "Thank you. I'll pass along your note to our driver. "
        },
        "UPDATE": {
            "prompt": \
                "I can identify your acount for you, I just need you to tell "\
                "me your current address",
            "received":
                "Thank you. I'll have someone update your account for you "\
                "right away."
        },
        "REGISTER": {
            "prompt": \
                "I can schedule you for pickup. What's your full address?"
            "received": \
                "Thanks. We'll be in touch shortly with a pickup date"
        }
    },
    "error": {
        "parse_question": \
            "I don't quite understand your question. ",
        "acct_lookup": \
            "I'm sorry, there seems to be a problem looking up "\
            "your account. We'll look into the matter for you.",
        "comprehension": \
            "Sorry, I don't understand your request. You'll have to guide "\
            "our conversation using keywords."
    }
}

#-------------------------------------------------------------------------------
def on_receive():
    '''Received an incoming SMS message.
    Cookies saved across requests: 'messagecount', 'awaiting'
    '''

    log_msg()
    msg_count = increment_msg_count()
    response = make_response()

    try:
        account = get_identity(response)
    except Exception as e:
        return send_reply(response, dialog['error']['acct_lookup'])
    else:
        save_msg()

    msg = get_msg()

    if new_convers():
        return handle_new_convers(response, msg)

    if awaiting_reply():
        return handle_reply(response, msg)
    elif awaiting_keywords():
        k = find_keyword(msg, get_cookie('listen_keywords'))

        if k:
            #set_cookie(response, 'listen_keywords', None)
            return handle_keyword(response, k)

    return guess_intent(response)

#-------------------------------------------------------------------------------
def guess_intent(response):
    '''Msg sent mid-conversation not understood as keyword or keyword reply.
    Use context clues to guess user intent.
    '''

    # Keep punctuation to get context
    msg = str(request.form['Body']).strip()

    # User asking a question?
    if '?' in msg:
        # TODO: flag msg as important

        return send_reply(
            response,
            dialog['error']['parse_question'] + dialog['user']['options'])

    msg = get_msg()

    # User ending conversation ("thanks")?
    if find_keyword(msg, CONVERSATION_ENDINGS):
        return send_reply(response, dialog['general']['thanks_reply'])

    return default_reply(response)

#-------------------------------------------------------------------------------
def handle_new_conversation(response):
    account = getattr(g, 'account', None)
    msg = str(request.form['Body']).strip()

    k = find_keyword(msg, KEYWORDS)

    if k:
        return handle_keyword(response, k)
    else:
        # Might be a conversation starter, or an unprompted reply
        # Send default reply
        return send_reply(
            get_default_reply(response, account=account),
            response
        )

#-------------------------------------------------------------------------------
def find_keyword(msg, listen_list):
    '''@msg: should be casted to string and stripped()
    '''

    cleaned_msg = msg.upper().translate(None, string.punctuation)
    words = cleaned_msg.split(' ')

    for word in words:
        if word in listen_list:
            return True

    return False

#-------------------------------------------------------------------------------
def get_identity(response):
    '''Per request global flask vars: g.acct_name, g.account, g.agency_conf
    '''

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

    g.account = account
    g.acct_name = get_name(account)
    g.agency_conf = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    logger.debug('set g.acct_name: %s', getattr(g, 'acct_name', None))

    set_cookie(response, 'etap_id', account['id'])

    return account

#-------------------------------------------------------------------------------
def get_msg():
    msg = str(request.form['Body']).strip()
    return msg.upper().translate(None, string.punctuation)

#-------------------------------------------------------------------------------
def awaiting_keywords():
    listen = get_cookie('listen_keywords')

    if type(listen) == list and len(listen) > 0:
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def handle_keyword(response, k):
    account = getattr(g, 'account', None)

    # Known user
    if account:
        if k == 'SKIP':
            # TODO: invoke pus.cancel_pickup()

            return send_reply(response,'')
        elif k == 'SCHEDULE':
            next_pu = etap.get_udf('Next Pickup Date', account)

            if not next_pu:
                return send_reply(
                    response,
                    dialog['error']['acct_lookup'])
            else:
                return send_reply(
                    response,
                    'Your next pickup is scheduled on ' +
                    etap.ddmmyyyy_to_dt(next_pu).strftime('%A, %B %-d') + '.')
        elif k == 'SUPPORT':
            return send_reply(
                response,
                dialog['k']['SUPPORT']['prompt'],
                listen_for = {'type':'reply', 'k':'SUPPORT'})
        elif k == 'INSTRUCTION':
            return send_reply(
                response,
                dialog['k']['INSTRUCTION']['prompt'],
                listen_for = {'type':'reply', 'k':'INSTRUCTION'})
    # Unregistered user
    else:
        if k == 'REGISTER':
            # TODO: prompt for address

            return send_reply(
                response, '',
                listen_for = {'type':'reply', 'k':'REGISTER'})
        elif k == 'UPDATE':
            # TODO: prompt for address

            return send_reply(
                response, '',
                listen_for = {'type':'reply', 'k', 'UPDATE'})

#-------------------------------------------------------------------------------
def awaiting_reply():
    if get_cookie('listen_reply'):
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def handle_reply(response):
    '''User was asked a question. Process their answer'''

    account = getattr(g, 'account', None)
    msg = str(request.form['Body']).strip()

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
def handle_unregistered(response):
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
def new_conversation():
    if get_cookie('messagecount') == 1:
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def tod_greeting():
    '''A simple hello at the beginning of a conversation'''

    hour = datetime.now().time().hour

    tod = ''

    if hour < 12:
        tod = 'morning'
    elif hour >= 12 and hour < 18:
        tod = 'afternoon'
    elif hour >= 18:
        tod = 'evening'

    return 'Good ' + tod + ' '

#-------------------------------------------------------------------------------
def default_reply(response):
    # TODO: Some other unprompted keyword?
    # Can't understand request. Send default reply.
    # TODO: If 3rd time sending default reply, offer assistance

    account = getattr(g, 'account', None)

    msg_count = get_cookie('messagecount')

    if msg_count == 1:
        reply += REPL_INTRO

    reply += REPL_DEFAULT

    return send_reply(reply, response)

#-------------------------------------------------------------------------------
def send_reply(response, dialog, listen_for=None):
    '''Add name contexts to beginning of dialog, create TWIML message
    '''

    if listen_for:
        set_cookie(response, 'listening_for', listen_for)
    else:
        # Parse reply-able keywords, save as cookies
        kw = []
        words = dialog.split(' ')
        for word in words:
            if word in KEYWORDS:
                kw.append(word)

        # listening_for may be empty list if we are ending conversation
        # and not expecting any reply/keyword
        set_cookie(response, 'listening_for', kw)

    agency = db.agencies.find_one({
        'twilio.sms.number':request.form['To']})

    if agency['name'] == 'vec':
        ASSISTANT_NAME = 'Alice'
        context = ASSISTANT_NAME + ': '
    else:
        context = ''

    name = getattr(g, 'acct_name', None)
    logger.debug('acct name: %s', name)

    if new_conversation():
        context += get_greeting()

        if name:
            context += ', ' + name + '. '
        else:
            context += '. '
    else:
        if name:
            context += name + ', '
            dialog = dialog[0].lower() + dialog[1:]

    twml = twiml.Response()

    context_dialog = context + dialog

    twml.message(context_dialog)

    logger.info('%s"%s"%s', bcolors.BOLD, context_dialog, bcolors.ENDC)

    response.data = str(twml)

    db.alice.update_one(
        {'from':request.form['From'], 'date': date.today().isoformat()},
        {'$push': {'messages': context_dialog}})

    return response

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

#-------------------------------------------------------------------------------
def log_msg():
    logger.debug(request.form.to_dict())

    logger.info('To Alice: %s"%s"%s (%s)',
                bcolors.BOLD, msg, bcolors.ENDC, request.form['From'])

#-------------------------------------------------------------------------------
def save_msg(agency):
    msg = get_msg()
    account = getattr(g, 'account', None)

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
def get_cookie(key):
    return request.cookies.get(key)

#-------------------------------------------------------------------------------
def set_cookie(response, k, v):
    expires=datetime.utcnow() + timedelta(hours=4)
    response.set_cookie(
        k,
        value=str(v),
        expires=expires.strftime('%a,%d %b %Y %H:%M:%S GMT'))

