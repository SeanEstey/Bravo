# app.alice.outgoing

from datetime import datetime
from twilio.rest import Client
from flask import g, request, current_app, make_response, session
from twilio.twiml.messaging_response import MessagingResponse
from app import get_keys
from app.lib.dt import to_local
from app.main import etapestry
from .dialog import dialog
from . import conversation
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def compose(body, to, acct_id=None, callback=None, ret_msg=False, event_log=True, mute=False):
    '''Send SMS message without access to Session.
    Can be called from outside blueprint. No access to flask session
    Returns twilio message object (not json serializable)
    '''

    alice = get_keys('alice')
    conf = get_keys('twilio')

    if alice.get('name'):
        body = '%s: %s' % (alice.get('name'), body)

    try:
        client = Client(
            conf['api']['sid'],
            conf['api']['auth_id'])
    except Exception as e:
        log.exception('Error creating Twilio client: %s', e.message)
        raise

    try:
        msg = client.messages.create(
            body = body,
            to = to,
            from_ = conf['sms']['number'],
            status_callback = callback)
    except Exception as e:
        log.exception('Error sending SMS message: %s', e.message)
        raise

    conversation.save_msg(body, mobile=to, acct_id=acct_id, direction='out')

    log.info(body, extra={'tag':'sms_msg'}) if event_log else log.debug(body, extra={'tag':'sms_msg'})

    return msg if ret_msg else msg.status

#-------------------------------------------------------------------------------
def reply(dialog, on_complete=None):
    """Send reply after receiving a message.
    Session data is present. Returns TwiML response.
    """

    session['ON_COMPLETE'] = on_complete
    self = session.get('SELF_NAME')
    name = get_name()
    greet = tod_greeting()
    context = ''

    if session['MESSAGECOUNT'] <= 1:
        context += '%s, %s. ' % (greet, name) if name else '%s. ' % (greet)
    elif session['MESSAGECOUNT'] > 1 and name:
        context += name + ', '
        dialog = dialog[0].lower() + dialog[1:]

    conversation.save_msg('%s: %s' % (self, context + dialog), user_session=True, direction='out')

    m_response = MessagingResponse()
    m_response.message(context + dialog)

    log.info('%s to %s: "%s"', self, session['FROM'][2:], context + dialog,
        extra={'tag':'sms_msg'})

    response = make_response()
    response.data = str(m_response)

    return response

#-------------------------------------------------------------------------------
def get_self_name(group_name):
    return g.db['groups'].find_one({'name':group_name})['alice']['name']

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
def send_welcome(etap_id):
    '''Called from client via end-user. Has request context
    '''

    try:
        # Very slow (~750ms-2200ms)
        acct = etapestry.call('get_account', data={'acct_id': int(etap_id)})
    except Exception as e:
        pass

    if not acct:
        raise Exception('No account id %s' % etap_id)

    if not etapestry.has_mobile(acct):
        raise Exception('No mobile number for acct id %s' % etap_id)

    from_ = get_keys(k='twilio')['sms']['number']
    self_name = get_keys(k='alice')['name']
    nf = acct['nameFormat']

    # Formats: None (0), Family (2), Business (2)
    if nf == 0 or nf == 2 or nf == 3:
        name = acct['name']
    # Format: Individual
    else:
        if acct['firstName']:
            name = acct['firstName']
        else:
            name = acct['name']

    msg = 'Hi %s, %s' % (name, dialog['user']['welcome'])

    r = compose(msg, etapestry.get_phone('Mobile', acct))

    return r.status
