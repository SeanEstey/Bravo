"""app.alice.incoming

Uses KVSession in place of flask session to store data server-side in MongoDB
Session expiry set in app.config.py, currently set to 60 min
Conversations permanently saved to MongoDB in bravo.alice
"""

import logging, string
from datetime import datetime, date, time, timedelta
from flask import request, make_response, g, session
from app import colors as c
from app.main.etapestry import EtapError
from . import keywords
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
            return make_reply(str(e))
    else:
        conversation.update()

    if parse_msg() == 'mute':
        conversation.mute()
        return 'OK'

    if session.get('MUTE_UNTIL'):
        if datetime.now() >= session['MUTE_UNTIL']:
            del session['MUTE_UNTIL']
        else:
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
        return make_reply(on_receive['dialog'], on_complete=on_complete)
    elif on_receive['action'] == 'event':
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
    if session.get('ACCOUNT'):
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
def make_reply(dialog_, on_complete=None):
    '''Add name contexts to beginning of dialog, create TWIML message
    Save this reply so we can know if the next user msg is responding to
    any keywords contained in it
    '''

    session['ON_COMPLETE'] = on_complete
    self = session.get('SELF_NAME')
    name = get_name()
    greet = tod_greeting()
    context = ''

    if session['MESSAGECOUNT'] <= 1:
        context += '%s, %s. ' % (greet, name) if name else '%s. ' % (greet)
    elif session['MESSAGECOUNT'] > 1 and name:
        context += name + ', '
        dialog_ = dialog_[0].lower() + dialog_[1:]

    conversation.save_msg('%s: %s' % (self, context + dialog_), user_session=True, direction='out')

    from twilio.twiml.messaging_response import MessagingResponse
    m_response = MessagingResponse()
    m_response.message(context + dialog_)

    log.info('%s to %s: "%s"', self, session['FROM'][2:], context + dialog_,
        extra={'tag':'sms_msg'})

    response = make_response()
    response.data = str(m_response)

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

    if not session.get('ACCOUNT'):
        return False

    account = session.get('ACCOUNT')
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
    return session.get('ON_COMPLETE')

#-------------------------------------------------------------------------------
def parse_msg(upper=False, rmv_punctn=False):
    '''Convert to str, strip spaces
    '''

    return str(request.form['Body'].encode('ascii', 'ignore')).strip()
