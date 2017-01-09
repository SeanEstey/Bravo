'''app.alice.brain
Uses KVSession in place of flask session to store data server-side in MongoDB
Session expiry set in app.config.py, currently set to 60 min
Conversations permanently saved to MongoDB in bravo.alice
'''

import logging
import string
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from datetime import datetime, date, time, timedelta
from flask import current_app, request, make_response, g, session
from .. import etap, utils, get_db, bcolors
from . import keywords
from .dialog import *
from .phrases import *
from .replies import *
from .helper import \
    check_identity, get_msg_count, inc_msg_count, log_msg, save_msg
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def receive_msg():
    '''Try to parse message.
    Return Twiml response
    '''

    inc_msg_count()
    log_msg()

    try:
        check_identity()
    except Exception as e:
        logger.error(str(e))
        return make_reply(dialog['error']['internal']['lookup'])

    save_msg()

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

    logger.debug('searching matches in %s', kws)

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
        logger.debug(
            'calling event handler %s.%s',
            on_receive['handler']['module'],
            on_receive['handler']['func'])

        try:
            module = __import__(on_receive['handler']['module'], fromlist='.')
            func = getattr(module, on_receive['handler']['func'])
            reply = func()
        except Exception as e:
            logger.error('%s failed: %s', on_receive['handler']['func'], str(e))
            logger.debug(str(e), exc_info=True)

            return make_reply(dialog['error']['internal']['default'], on_complete=on_complete)

        return make_reply(reply, on_complete=on_complete)

#-------------------------------------------------------------------------------
def handle_answer():
    '''Received expected reply. Call event handler for listener key
    '''

    do = session.get('on_complete')

    if do['action'] == 'dialog':
        reply = do['dialog']
    elif do['action'] == 'event':
        logger.debug(
            'calling event handler %s.%s',
            do['handler']['module'],
            do['handler']['func'])

        try:
            mod = __import__(do['handler']['module'], fromlist='.')
            func = getattr(mod, do['handler']['func'])
            reply = func()
        except Exception as e:
            logger.error(\
                'event %s.%s failed: %s',
                do['handler']['module'],
                do['handler']['func'],
                str(e))

            return make_reply(dialog['error']['internal']['default'])

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

    twml = twiml.Response()
    twml.message(context + _dialog)

    logger.info('%s"%s"%s', bcolors.BOLD, context + _dialog, bcolors.ENDC)

    response = make_response()
    response.data = str(twml)

    db = get_db()

    db.alice.update_one(
        {'from': request.form['From'],
        'date': date.today().isoformat()},
        {'$push': {
            'messages': context + _dialog}})

    return response

#-------------------------------------------------------------------------------
def compose_msg(body, to, agency, conf, callback=None):
    '''Compose SMS message to recipient
    Can be called from outside blueprint. No access to flask session
    '''

    self_name = get_self_name(agency)

    if self_name:
        body = '%s: %s' % (self_name, body)

    try:
        client = TwilioRestClient(
            conf['api']['sid'],
            conf['api']['auth_id'])
    except Exception as e:
        logger.error(e)
        logger.debug(e, exc_info=True)
        raise

    try:
        msg = client.messages.create(
            body = body,
            to = to,
            from_ = conf['sms']['number'],
            status_callback = callback)
    except Exception as e:
        logger.error(e)
        logger.debug(e, exc_info=True)
        raise
    else:
        logger.info('returning msg')
        return msg

    logger.info('returning msg status')
    return msg.status

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
def get_self_name(agency):
    db = get_db()
    return db.agencies.find_one({'name':agency})['alice']['name']

#-------------------------------------------------------------------------------
def expecting_answer():
    return session.get('on_complete')

#-------------------------------------------------------------------------------
def get_msg():
    '''Convert from unicode to prevent weird parsing issues'''

    return str(request.form['Body']).strip()
