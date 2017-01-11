'''app.alice.incoming

Uses KVSession in place of flask session to store data server-side in MongoDB
Session expiry set in app.config.py, currently set to 60 min
Conversations permanently saved to MongoDB in bravo.alice
'''

import logging
import string
from twilio import twiml
from datetime import datetime, date, time, timedelta
from flask import current_app, request, make_response, g, session
from .. import etap, utils, bcolors
from app.etap import EtapError
from . import keywords
from .dialog import *
from .phrases import *
from .replies import *
from .helper import \
    has_session, create_session, update_session, get_msg_count, inc_msg_count,\
    get_msg, log_msg
log = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def receive():
    '''Try to parse message.
    Return Twiml response
    '''

    inc_msg_count()
    log_msg()

    if not has_session():
        try:
            create_session()
        except EtapError as e:
            return make_reply(str(e))
        except Exception as e:
            log.debug(str(e), exc_info=True)
            log.error(str(e))
            return make_reply(dialog['error']['unknown'])

    update_session()

    kws = find_kw_matches(get_msg(), session.get('valid_kws'))

    if kws:
        return handle_keyword(kws[0])
    elif expecting_answer():
        return handle_answer()
    else:
        return handle_unknown()

#-------------------------------------------------------------------------------
def find_kw_matches(message, kws):
    '''@message: either incoming or outgoing text
    '''

    log.debug('searching matches in %s', kws)

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
def find_phrase_match(phrases):
    '''@phrases: list of >= 1 word strings
    '''

    message = get_msg().upper()

    return message in phrases

#-------------------------------------------------------------------------------
def handle_keyword(kw, handler=None):
    '''Received msg with a keyword command. Send appropriate reply and
    set any necessary listeners.
    '''

    if handler:
        _handler = handler
    elif session.get('account'):
        _handler = keywords.user[kw]
    else:
        _handler = keywords.anon[kw]

    on_receive = _handler.get('on_receive')
    on_complete = _handler.get('on_complete')

    if on_receive['action'] == 'reply':
        return make_reply(on_receive['dialog'], on_complete=on_complete)
    elif on_receive['action'] == 'event':
        log.debug(
            'calling event handler %s.%s',
            on_receive['handler']['module'],
            on_receive['handler']['func'])


        try:
            module = __import__(on_receive['handler']['module'], fromlist='.')
            func = getattr(module, on_receive['handler']['func'])
            reply = func()
        except Exception as e:
            log.error('%s failed: %s', on_receive['handler']['func'], str(e))
            log.debug(str(e), exc_info=True)

            return make_reply(dialog['error']['unknown'], on_complete=on_complete)

        return make_reply(reply, on_complete=on_complete)

#-------------------------------------------------------------------------------
def handle_answer():
    '''Received expected reply. Call event handler for listener key
    '''

    do = session.get('on_complete')

    if do['action'] == 'dialog':
        reply = do['dialog']
    elif do['action'] == 'event':
        log.debug(
            'calling event handler %s.%s',
            do['handler']['module'],
            do['handler']['func'])

        try:
            mod = __import__(do['handler']['module'], fromlist='.')
            func = getattr(mod, do['handler']['func'])
            reply = func()
        except Exception as e:
            log.error(\
                'event %s.%s failed: %s',
                do['handler']['module'],
                do['handler']['func'],
                str(e))

            return make_reply(dialog['error']['unknown'])

    return make_reply(reply)

#-------------------------------------------------------------------------------
def handle_unknown():
    '''
    '''

    # Try to identify non-command keys/phrases

    if guess_intent():
        return make_reply(guess_intent())

    # Cannot parse message. Send default response

    if session.get('account'):
        return make_reply(dialog['user']['options'])
    else:
        return make_reply(dialog['anon']['options'])

#-------------------------------------------------------------------------------
def guess_intent():
    '''Use some context clues to guess user intent.'''

    # Lookup known phrases (ie 'thank you')

    if find_phrase_match(ending_chat):
        return dialog['general']['welcome_reply']

    # Lookup general keyword replies

    kw = find_kw_matches(get_msg(), replies.keys())

    if kw:
        return replies[kw[0]]

    # No keywords or phrases indentified. Is user asking a question?

    if '?' in get_msg():
        return '%s %s' %(
            dialog['error']['parse']['question'],
            dialog['user']['options'])

    return False

#-------------------------------------------------------------------------------
def make_reply(_dialog, on_complete=None):
    '''Add name contexts to beginning of dialog, create TWIML message
    Save this reply so we can know if the next user msg is responding to
    any keywords contained in it
    '''

    session['on_complete'] = on_complete
    name = get_name()
    greet = tod_greeting()
    context = '%s: '% session.get('self_name') if session.get('self_name') else ''

    if get_msg_count() == 1:
        context += '%s, %s. ' % (greet, name) if name else '%s. ' % (greet)
    else:
        if name:
            context += name + ', '
            _dialog = _dialog[0].lower() + _dialog[1:]

    session['messages'].append(context + _dialog)

    twml = twiml.Response()
    twml.message(context + _dialog)

    log.info('%s"%s"%s', bcolors.BOLD, context + _dialog, bcolors.ENDC)

    response = make_response()
    response.data = str(twml)

    return response

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
def get_name():
    '''Returns account 'name' or 'firstName' for registered users,
    None for unregistered users'''

    if not session.get('account'):
        return False

    account = session.get('account')

    nf = account['nameFormat']

    # Formats: None (0), Family (2), Business (2)
    if nf == 0 or nf == 2 or nf == 3:
        return account['name']

    # Format: Individual (1)

    if account['firstName']:
        return account['firstName']
    else:
        return account['name']

#-------------------------------------------------------------------------------
def expecting_answer():
    return session.get('on_complete')
