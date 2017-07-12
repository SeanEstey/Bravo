# app.alice.outgoing

from datetime import datetime
from twilio.rest import Client
from flask import g, request, current_app
from app import get_keys
from app.lib.dt import to_local
from app.main import etapestry
from .dialog import dialog
from . import conversation
from logging import getLogger
log = getLogger(__name__)

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

#-------------------------------------------------------------------------------
def compose(body, to, callback=None, ret_msg=False, event_log=True, mute=False):
    '''Compose SMS message to recipient
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

    conversation.save_msg(body, mobile=to, direction='out')

    if mute:
        log.debug('mute=%s, type=%s', mute, type(mute))
        conversation.mute(mobile=to)

    log.info(body, extra={'tag':'sms_msg'}) if event_log else log.debug(body, extra={'tag':'sms_msg'})

    return msg if ret_msg else msg.status

#-------------------------------------------------------------------------------
def get_self_name(group_name):
    return g.db['groups'].find_one({'name':group_name})['alice']['name']
