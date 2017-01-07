'''app.alice.brain'''

import logging
import string
from twilio import twiml
from datetime import datetime, date, time, timedelta
from flask import current_app, request, make_response, g, session
from .. import etap, utils, db, bcolors
from .conf import anon_keywords, user_keywords, dialog
from .helper import \
    check_identity, log_msg, save_msg, get_cookie, set_cookie, inc_msg_count
logger = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def receive_msg():
    '''Received an incoming SMS message.
    User info including eTap account held in server-side session for 60 min
    '''

    log_msg()
    msg_count = inc_msg_count()
    r = make_response()

    try:
        check_identity()
    except Exception as e:
        logger.error(str(e))
        return send_reply(r, dialog['error']['acct_lookup'])

    save_msg()

    message = get_msg()

    kws = find_kw_matches(message, session.get('valid_kws'))

    if kws:
        return handle_keyword(r, kws[0])
    elif expecting_answer():
        return handle_answer(r)
    else:
        return handle_unknown(r)

#-------------------------------------------------------------------------------
def expecting_answer():
    '''Is the message a specific reply to a keyword['on_receive'] dialog?'''

    if session.get('on_complete'):
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def find_kw_matches(message, kws):
    '''@message: either incoming or outgoing text
    '''

    # Remove punctuation, make upper case, split into individual words
    words = message.upper().translate(
        None,
        string.punctuation
    ).split(' ')

    matches = []

    for word in words:
        if word in kws:
            matches.append(word)

    return matches

#-------------------------------------------------------------------------------
def get_msg():
    '''Convert from unicode to prevent weird parsing issues'''

    return str(request.form['Body']).strip()

#-------------------------------------------------------------------------------
def handle_keyword(response, kw):
    '''Received msg with a keyword command. Send appropriate reply and
    set any necessary listeners.
    '''

    on_receive = session['valid_kws'][kw]['on_receive']
    on_complete = session['valid_kws'][kw].get('on_complete')

    if on_receive['action'] == 'reply':
        return send_reply(r, on_receive['dialog'], on_complete=on_complete)
    elif on_receive['action'] == 'event':
        function = getattr(
            on_receive['handler']['module'],
            on_receive['handler']['func'])

        try:
            reply = function()
        except Exception as e:
            logger.error('%s failed: %s', on_receive['handler']['func'], str(e))

            return send_reply(r, dialog['error']['unknown'], on_complete=on_complete)

#-------------------------------------------------------------------------------
def handle_answer(response):
    '''Received expected reply. Call event handler for listener key
    '''

    on_complete = session.get('on_complete')

    if on_complete['action'] == 'dialog':
        return send_reply(r, on_complete['dialog'])
    elif on_complete['action'] == 'event':
        module = on_complete['handler']['module']
        func = on_complete['handler']['func']

        try:
            return send_reply(r, getattr(module, func)())
        except Exception as e:
            logger.error('event %s.%s failed: %s', module, func, str(e))

            return send_reply(r, dialog['error']['unknown'])

#-------------------------------------------------------------------------------
def handle_unknown(response):
    '''Unable to understand message. Send default reply.
    '''

    if guess_intent():
        return send_reply(r, guess_intent())

    if session.get('account'):
        return send_reply(r, dialog['user']['options'])
    else:
        return send_reply(r, dialog['anon']['options'])

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
def send_reply(r, _dialog, on_complete=None):
    '''Add name contexts to beginning of dialog, create TWIML message
    Save this reply so we can know if the next user msg is responding to
    any keywords contained in it
    '''

    if on_complete:
        session['on_complete'] = on_complete
    else:
        session['on_complete'] = None

    conf = session.get('conf')

    if conf['name'] == 'vec':
        ASSISTANT_NAME = 'Alice'
        context = ASSISTANT_NAME + ': '
    else:
        context = ''

    name = get_name()

    if first_reply():
        context += tod_greeting()

        if name:
            context += ', ' + name + '. '
        else:
            context += '. '
    else:
        if name:
            context += name + ', '
            _dialog = _dialog[0].lower() + _dialog[1:]

    twml = twiml.Response()

    twml.message(context + _dialog)

    logger.info('%s"%s"%s', bcolors.BOLD, context + _dialog, bcolors.ENDC)

    r.data = str(twml)

    db.alice.update_one(
        {'from': request.form['From'],
        'date': date.today().isoformat()},
        {'$push': {
            'messages': context + _dialog}})

    return r

#-------------------------------------------------------------------------------
def guess_intent():
    '''Msg sent mid-conversation not understood as keyword or keyword reply.
    Use context clues to guess user intent.
    '''

    # User asking a question?

    if '?' in get_msg():
        return dialog['error']['parse_question'] + dialog['user']['options']

    # User ending conversation? ("thanks")

    matches = find_kw_matches(get_msg(), conversation_endings):

    if matches:
        return dialog['general']['thanks_reply']

    return False
