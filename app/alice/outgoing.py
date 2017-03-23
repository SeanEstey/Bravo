'''app.alice.outgoing'''
import logging
import cPickle as pickle
from datetime import datetime
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException
from flask import g, request
from app import get_logger, get_keys, kv_store
from app.main import etap
from app.lib.logger import colors as c
from app.lib.dt import to_local
from .dialog import dialog
from .session import store_sessions
log = get_logger('alice.out')


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

    return r.status

#-------------------------------------------------------------------------------
def compose(agcy, body, to, callback=None, find_session=False, event_log=False):
    '''Compose SMS message to recipient
    Can be called from outside blueprint. No access to flask session
    Returns twilio message object (not json serializable)
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
        if event_log:
            log.info('%s"%s"%s', c.BOLD, body, c.ENDC)
        else:
            log.debug('%s"%s"%s', c.BOLD, body, c.ENDC)

    if not find_session:
        return msg

    # Store the new message in the user's session

    chats = g.db.chatlogs.find({'from':to}).sort('last_msg_dt',-1).limit(1)

    if chats.count() == 0:
        return msg.status

    chat = chats.next()

    try:
        sess = pickle.loads(kv_store.get(chat['sess_id']))
    except Exception as e:
        sess = None
    else:
        sess['messages'].append(body)
        sess['last_msg_dt'] = to_local(datetime.now())
        kv_store.put(chat['sess_id'], pickle.dumps(sess))
        log.debug('updated sess_id=%s with outgoing msg', chat['sess_id'])

    return msg.status

#-------------------------------------------------------------------------------
def get_self_name(agency):
    return g.db.agencies.find_one({'name':agency})['alice']['name']
