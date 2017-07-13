"""app.alice.incoming

Uses KVSession in place of flask session to store data server-side in MongoDB
Session expiry set in app.config.py, currently set to 60 min
Conversations permanently saved to MongoDB in bravo.alice
"""

import logging, string
from datetime import datetime, date, time, timedelta
from flask import request, g, session
from app import colors as c
from app.main.etapestry import EtapError
from . import keywords
from .outgoing import reply
from .dialog import *
from .phrases import *
from .replies import *
from . import conversation
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def receive():
    '''Try to parse message.
    Return Twiml response
    '''

    if not conversation.exists():
        try:
            conversation.new()
        except EtapError as e:
            return reply(str(e))
    else:
        conversation.update()

    if conversation.is_muted():
        return 'OK'

    kws = find_kw_matches(parse_msg(), session.get('VALID_KWS'))

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

    # Remove punctuation, make upper case, split into individual words
    words = message.upper().translate(
        None,
        string.punctuation
    ).split()

    matches = []

    for word in words:
        if word in kws:
            matches.append(word)

    return matches

#-------------------------------------------------------------------------------
def find_phrase_match(phrases):
    '''@phrases: list of >= 1 word strings
    '''
    message = parse_msg().upper().translate(None, string.punctuation)
    return message in phrases

#-------------------------------------------------------------------------------
def handle_keyword(kw, handler=None):
    '''Received msg with a keyword command. Send appropriate reply and
    set any necessary listeners.
    '''

    if handler:
        _handler = handler
    elif session.get('ACCOUNT'):
        _handler = keywords.user[kw]
    else:
        _handler = keywords.anon[kw]

    on_receive = _handler.get('on_receive')
    on_complete = _handler.get('on_complete')

    if on_receive['action'] == 'reply':
        return reply(on_receive['dialog'], on_complete=on_complete)
    elif on_receive['action'] == 'event':
        try:
            module = __import__(on_receive['handler']['module'], fromlist='.')
            func = getattr(module, on_receive['handler']['func'])
            body = func()
        except Exception as e:
            log.error('%s failed: %s', on_receive['handler']['func'], str(e))
            log.debug(str(e), exc_info=True)

            return reply(dialog['error']['unknown'], on_complete=on_complete)

        return reply(body, on_complete=on_complete)

#-------------------------------------------------------------------------------
def handle_answer():
    '''Received expected reply. Call event handler for listener key
    '''

    do = session.get('ON_COMPLETE')

    if do['action'] == 'dialog':
        reply = do['dialog']
    elif do['action'] == 'event':
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

            return reply(dialog['error']['unknown'])

    return reply(reply)

#-------------------------------------------------------------------------------
def handle_unknown():
    '''
    '''

    # Try to identify non-command keys/phrases
    if guess_intent():
        return reply(guess_intent())

    # Cannot parse message. Send default response
    if session.get('ACCOUNT'):
        return reply(dialog['user']['options'])
    else:
        return reply(dialog['anon']['options'])

#-------------------------------------------------------------------------------
def guess_intent():
    '''Use some context clues to guess user intent.'''

    # Lookup known phrases (ie 'thank you')

    if find_phrase_match(ending_chat):
        return dialog['general']['welcome_reply']

    # Lookup general keyword replies

    kw = find_kw_matches(parse_msg(), replies.keys())

    if kw:
        return replies[kw[0]]

    # No keywords or phrases indentified. Is user asking a question?

    if '?' in parse_msg():
        return '%s %s' %(
            dialog['error']['parse']['question'],
            dialog['user']['options'])

    return False

#-------------------------------------------------------------------------------
def expecting_answer():
    return session.get('ON_COMPLETE')

#-------------------------------------------------------------------------------
def parse_msg(upper=False, rmv_punctn=False):
    '''Convert to str, strip spaces
    '''

    return str(request.form['Body'].encode('ascii', 'ignore')).strip()
