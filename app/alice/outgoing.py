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
            'get_acct',
            get_keys(k='etapestry'),
            {'acct_id': int(etap_id)}
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
        g.user.agency,
        msg,
        etap.get_phone('Mobile', acct))

    log.info('%s"%s"%s', bcolors.BOLD, msg, bcolors.ENDC)

    return r.status

#-------------------------------------------------------------------------------
def compose(agcy, body, to, callback=None):
    '''Compose SMS message to recipient
    Can be called from outside blueprint. No access to flask session
    '''

    alice = get_keys('alice',agcy=agcy)

    if alice.get('name'):
        body = '%s: %s' % (alice.get('name'), body)

    conf = get_keys('twilio',agcy=agcy)

    try:
        client = TwilioRestClient(
            conf['api']['sid'],
            conf['api']['auth_id'])
    except Exception as e:
        log.error(e)
        log.debug(e, exc_info=True)
        raise

    try:
        msg = client.messages.create(
            body = body,
            to = to,
            from_ = conf['sms']['number'],
            status_callback = callback)
    except Exception as e:
        log.error(e)
        log.debug(e, exc_info=True)
        raise
    else:
        #log.info('returning msg')
        return msg

    #log.info('returning msg status')
    return msg.status

#-------------------------------------------------------------------------------
def get_self_name(agency):
    return g.db.agencies.find_one({'name':agency})['alice']['name']
