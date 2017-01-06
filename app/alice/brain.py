'''app.alice.brain'''

import logging
import string
from twilio import twiml
from datetime import datetime, date, time, timedelta
from flask import current_app, request, make_response, g
from .. import etap, utils, db, bcolors
from .conf import actions, dialog
from .helper import \
    get_identity, log_msg, save_msg, get_cookie, set_cookie, inc_msg_count
logger = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def on_receive():
    '''Received an incoming SMS message.
    Cookies saved across requests: 'messagecount', 'awaiting'
    '''

    log_msg()
    msg_count = inc_msg_count()
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

    if listening_for('keyword'):
        matches = find_matches(msg, get_cookie('listen_kws'))

        if matches:
            if len(matches) == 1:
                return handle_keyword(response, maches[0])
            elif len(matches) > 1:
                # Fixme. Oh-oh...
                return False
        else:
            # Fixme. is it another unexpected keyword?
            return False
    elif listening_for('reply'):
        return handle_reply(response)

    return guess_intent(response)

#-------------------------------------------------------------------------------
def handle_new_conversation(response):
    account = getattr(g, 'account', None)
    msg = str(request.form['Body']).strip()

    k = parse_keyword(msg, KEYWORDS)

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
def find_matches(message, listen_list):
    '''@msg: should be casted to string and stripped()
    '''

    # Remove punctuation, make upper case, split into individual words
    words = message.upper().translate(
        None,
        string.punctuation
    ).split(' ')

    matches = []

    for word in words:
        if word in listen_list:
            matches.append(word)

    if len(matches) > 0:
        return matches
    else:
        return False

#-------------------------------------------------------------------------------
def get_msg():
    return str(request.form['Body']).strip()

#-------------------------------------------------------------------------------
def handle_keyword(response, k):
    '''Received msg with a keyword command. Send appropriate reply and
    set any necessary listeners.
    '''

    account = getattr(g, 'account', None)

    cmd = actions[k]['on_keyword']

    reply = ''

    # Either call event handler or return dialog for keyword
    if cmd.keys()[0] == 'handler':
        handler_func = getattr(
            cmd['handler']['module'],
            cmd['handler']['func'])

        try:
            reply = handler_func()
        except Exception as e:
            logger.error('%s failed: %s', cmd['handler']['func'], str(e))
            return False
    elif cmd.keys()[0] == 'dialog':
        reply = cmd['dialog']

    # Outcome A (reply with no keywords, clear listeners)
    if not actions[k].get('on_reply'):
        set_cookie(response, 'listen_kws', None)
        set_cookie(response, 'listen_for', None)

        return send_reply(response, reply)

    kws = find_matches(reply, actions.keys())

    # Outcome B (reply w/o keywords, listen for whole response)
    if not kws:
        set_cookie(response, 'last_kw', kws)
        set_cookie(response, 'listen_for', 'reply')
        set_cookie(response, 'listen_kws', None)
        return send_reply(response, reply)

    # Outcome C (reply w/ keywords, listen for them)
    set_cookie(response, 'last_kw', k)
    set_cookie(response, 'listen_for', 'keyword')
    set_cookie(response, 'listen_kws', kw)
    return send_reply(response, reply)

#-------------------------------------------------------------------------------
def handle_reply(response):
    '''Received expected reply. Call event handler for listener key
    '''

    kw = get_cookie('last_kw')

    handler_func = getattr(
        actions[kw]['on_reply']['handler']['module'],
        actions[kw]['on_reply']['handler']['func'])

    try:
        reply = handler_func()
    except Exception as e:
        logger.error('%s failed: %s', kw, str(e))
        return False

    # clear listeners
    set_cookie(response, 'listen_kws', None)
    set_cookie(response, 'listen_for', None)

    return send_reply(response, reply)

#-------------------------------------------------------------------------------
def listening_for(_type):
    '''@_type: ['keyword', 'reply', None]
    '''

    if get_cookie('listen_for'):
        if get_cookie('listen_for') == _type:
            return True

    return False

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
def send_reply(response, message):
    '''Add name contexts to beginning of dialog, create TWIML message
    '''

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
            message = message[0].lower() + message[1:]

    twml = twiml.Response()

    context_message = context + message

    twml.message(context_message)

    logger.info('%s"%s"%s', bcolors.BOLD, context_dialog, bcolors.ENDC)

    response.data = str(twml)

    db.alice.update_one(
        {'from':request.form['From'], 'date': date.today().isoformat()},
        {'$push': {'messages': context_message}})

    return response

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
    if parse_keyword(msg, CONVERSATION_ENDINGS):
        return send_reply(response, dialog['general']['thanks_reply'])

    return default_reply(response)
