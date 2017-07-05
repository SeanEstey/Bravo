'''app.alice.session'''
import logging, sys
from flask import request, current_app, g, request, session
from flask_kvsession import SessionID
from bson.objectid import ObjectId
import cPickle as pickle
from datetime import datetime, date, timedelta
from app.main.etapestry import is_active, EtapError
from app.main.tasks import create_rfu
from app.lib.dt import to_local
from app.lib.utils import obj_vars
from . import keywords
from .util import related_notific, lookup_acct, event_begun
from .dialog import *
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def has_session():
    return True if session.get('type') == 'alice_chat' else False

#-------------------------------------------------------------------------------
def create_session():
    '''Init session vars after receiving incoming SMS msg'''

    mobile = str(request.form['From'])
    msg = request.form['Body']
    conf = g.db['groups'].find_one({'twilio.sms.number':request.form['To']})
    g.group = conf['name']
    session.permanent = True
    session.update({
        'type': 'alice_chat',
        'from': mobile,
        'date': date.today().isoformat(),
        'group': g.group,
        'conf': conf,
        'self_name': conf['alice']['name'],
        'last_msg_dt': to_local(dt=datetime.now()),
        'expiry_dt': datetime.now() + current_app.config['PERMANENT_SESSION_LIFETIME']
    })

    try:
        acct = lookup_acct(mobile)
    except Exception as e:
        log.debug('Uregistered user')
        sys.exc_clear()
        session.update({
            'anon_id':  str(ObjectId()),
            'valid_kws': keywords.anon.keys()
        })
        save_msg(msg, direction="in")
        return

    log.debug('Registered user %s', acct.get('name'))

    session.update({
        'account':acct,
        'valid_kws': keywords.user.keys()
    })

    # Replying to notification?
    notific = related_notific(log_error=False)
    if notific:
        g.db['notifics'].update_one({'_id':notific['_id']},{'$set':{'tracking.reply':msg}})
        session.update({
            'notific_id': notific['_id'],
            'valid_notific_reply': not event_begun(notific)
        })

    if not is_active(acct):
        log.error("Acct inactive (etap_id=%s)", acct['id'])
        raise EtapError(dialog['error']['etap']['inactive'])

    save_msg(msg, direction="in")

#-------------------------------------------------------------------------------
def save_msg(text, mobile=None, direction=None):
    '''@mobile: if sending msg outside of session'''

    phone = session.get('from', mobile)
    acct = session.get('account', {})

    # TODO: should be able to do upsert here. condense these queries

    if not g.db['chatlogs'].find_one({'mobile':phone}):
        g.db['chatlogs'].insert_one({
            'group':g.group,
            'mobile': phone,
            'acct_id': acct.get('id', None),
            'last_message': datetime.utcnow(),
            'messages': [{
                'timestamp': datetime.utcnow(),
                'message': text,
                'direction': direction
            }]
        })
    else:
        g.db['chatlogs'].update_one(
            {'mobile': phone},
            {'$push': {'messages': {
                'timestamp': datetime.utcnow(),
                'message': text,
                'direction': direction
             }},
             '$set': {
                'acct_id': acct.get('id', None),
                'group':g.group,
                'last_message':datetime.utcnow()
              }
           },
           True)

#-------------------------------------------------------------------------------
def dump_session(key=None, to_dict=False):
    '''dumps the current chat session. If key specified, dumps session
    from kv_store
    @key: kv_store key
    '''

    omit = [
        'account', 'conf', '_flashes', '_id', '_fresh', '_permanent', 'on_complete']

    if not key:
        # Get current session
        sess = session.copy()
    else:
        sess = pickle.loads(current_app.kv_store.get(key)).copy()

    for k in omit:
        sess.pop(k, None)

    if to_dict:
        return sess
    else:
        return 'session dump (id=%s):\n%s' % (key, obj_vars(sess))

#-------------------------------------------------------------------------------
def dump_sessions():
    '''
    '''

    lifetime = current_app.config['PERMANENT_SESSION_LIFETIME']
    n_sess = len(current_app.kv_store.keys())
    n_chats = 0
    n_chats_expired = 0
    n_chats_active = 0
    now = datetime.utcnow()
    dumps = []

    for key in current_app.kv_store.keys():
        sess = pickle.loads(current_app.kv_store.get(key))

        if sess.get('type') == 'alice_chat':
            n_chats += 1
            sid = SessionID.unserialize(key)

            if sid.has_expired(lifetime, now):
                n_chats_expired += 1
            else:
                n_chats_active += 1

            dumps.append(dump_session(key, to_dict=True))

    return {
        'sessions': n_sess,
        'chats': n_chats,
        'active_chats': n_chats_active,
        'expired_chats': n_chats_expired,
        'dumps': dumps
    }

#-------------------------------------------------------------------------------
def del_expired_session(key, force=False):
    m = current_app.kv_ext.key_regex.match(key)

    if m:
        sid = SessionID.unserialize(key)
        now = datetime.utcnow()

        lifetime = current_app.config['PERMANENT_SESSION_LIFETIME']

        if force:
            current_app.kv_store.delete(key)
        elif sid.has_expired(lifetime, now):
                #log.debug('sess expired. deleted (key=%s)', key)
                current_app.kv_store.delete(key)
        else:
            #log.debug('sess not yet expired (key=%s)', key)
            pass

#-------------------------------------------------------------------------------
def wipe_sessions():
    '''Destroy all sessions
    '''

    n_start = len(current_app.kv_store.keys())

    for key in current_app.kv_store.keys():
        del_expired_session(key, force=True)

    n_end = len(current_app.kv_store.keys())

    log.debug('wiped sessions, start=%s, end=%s', n_start, n_end)

    return n_start


