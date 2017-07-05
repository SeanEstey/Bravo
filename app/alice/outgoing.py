'''app.alice.outgoing'''
import cPickle as pickle
from datetime import datetime
from twilio.rest import Client
from flask import g, request, current_app
from app import get_keys
from app.main import etapestry
from app.lib.dt import to_local
from .dialog import dialog
from .session import save_msg
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
def compose(body, to, callback=None, find_session=False, event_log=True):
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

    save_msg(body, mobile=to, direction='out')

    log.info(body, extra={'tag':'sms_msg'}) if event_log else log.debug(body, extra={'tag':'sms_msg'})

    # TODO Delete this code once Alice chat view is complete

    if not find_session:
        return msg

    # Store the new message in the user's session

    chats = g.db.chatlogs.find({'from':to}).sort('last_msg_dt',-1).limit(1)

    if chats.count() == 0:
        return msg.status

    chat = chats.next()

    try:
        sess = pickle.loads(current_app.kv_store.get(chat['sess_id']))
    except Exception as e:
        sess = None
    else:
        sess['messages'].append(body)
        sess['last_msg_dt'] = to_local(datetime.now())
        current_app.kv_store.put(chat['sess_id'], pickle.dumps(sess))
        log.debug('updated sess_id=%s with outgoing msg', chat['sess_id'])

    log.debug('msg.status=%s', msg.status)
    return msg.status

#-------------------------------------------------------------------------------
def get_self_name(group_name):
    return g.db['groups'].find_one({'name':group_name})['alice']['name']
