'''app.alice.outgoing'''
import logging
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException
from flask import g, request
from .. import etap
from app.utils import bcolors
from .. import get_keys
from .dialog import dialog
log = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def send_welcome(etap_id):
    '''Called from client via end-user. Has request context
    '''

    try:
        # Very slow (~750ms-2200ms)
        acct = etap.call(
            'get_account',
            get_keys(k='etapestry'),
            {'account_number': int(etap_id)}
        )
    except Exception as e:
        pass

    if not acct:
        raise Exception('No account id %s' % etap_id)

    if not etap.has_mobile(acct):
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

    r = compose(
        msg,
        etap.get_phone('Mobile', acct),
        from_,
        self_name,
        get_keys(k='twilio'))

    log.info('%s"%s"%s', bcolors.BOLD, msg, bcolors.ENDC)

    return r.status

#-------------------------------------------------------------------------------
def compose(body, to, from_, self_name, t_keys, status_callback=None):
    '''Compose SMS message to recipient
    Can be called from outside blueprint. No access to flask session
    '''

    if self_name:
        body = '%s: %s' % (self_name, body)

    try:
        client = TwilioRestClient(
            t_keys['api']['sid'],
            t_keys['api']['auth_id'])
    except Exception as e:
        log.error(e)
        log.debug(e, exc_info=True)
        raise

    try:
        msg = client.messages.create(
            body = body,
            to = to,
            from_ = from_, #t_conf['sms']['number'],
            status_callback = status_callback)
    except Exception as e:
        log.error(e)
        log.debug(e, exc_info=True)
        raise
    else:
        log.info('returning msg')
        return msg

    log.info('returning msg status')
    return msg.status

#-------------------------------------------------------------------------------
def get_self_name(agency):
    return g.db.agencies.find_one({'name':agency})['alice']['name']
