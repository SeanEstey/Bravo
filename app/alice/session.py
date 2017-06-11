'''app.alice.session'''
import logging, sys
from flask import request, current_app, g, request, session
from flask_kvsession import SessionID
from bson.objectid import ObjectId
import cPickle as pickle
from datetime import datetime, date, timedelta
from app.main.etap import is_active, EtapError
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
    if session.get('type') == 'alice_chat':
        return True

#-------------------------------------------------------------------------------
def create_session():

    from_ = str(request.form['From'])
    msg = request.form['Body']
    life_duration = current_app.config['PERMANENT_SESSION_LIFETIME']
    conf = g.db['groups'].find_one({'twilio.sms.number':request.form['To']})

    # Init session data

    session.permanent = True
    session['type'] = 'alice_chat'
    session['from'] = from_
    session['date'] = date.today().isoformat()
    session['messages'] = [msg]
    session['agcy'] = g.group = conf['name']
    session['conf'] = conf
    session['self_name'] = conf['alice']['name']
    session['last_msg_dt'] = to_local(dt=datetime.now())
    session['expiry_dt'] = datetime.now() + life_duration

    try:
        acct = lookup_acct(from_, session.get('agcy'))
    except EtapError as e:
        sys.exc_clear()
        acct = None

    if not acct:
        # Unregistered user
        session['anon_id'] = anon_id = str(ObjectId())
        session['valid_kws'] = keywords.anon.keys()

        create_rfu.delay(
            session.get('agcy'),
            'No eTap acct linked to this mobile number.\nMessage: "%s"' % msg,
            options = {
                'Account': 'Mobile: %s' % from_})

        log.debug('Uregistered user')
    else:
        # Registered user
        session['account'] = acct
        session['valid_kws'] = keywords.user.keys()

        notific = related_notific(log_error=False)

        # Is there a notification user might be replying to?
        if notific:
            g.db.notifics.update_one({'_id':notific['_id']},{'$set':{'tracking.reply':msg}})

            session['notific_id'] = notific['_id']
            session['messages'].insert(0, notific['tracking']['body'])
            session['valid_notific_reply'] = not event_begun(notific)

            #log.debug('Reply linked to notific_id=%s. valid=%s',
            #    notific['_id'], session.get('valid_notific_reply'))

        log.debug('Registered user %s', acct.get('name'))

        if not is_active(acct):
            log.error("Acct inactive (etap_id=%s)", acct['id'])
            raise EtapError(dialog['error']['etap']['inactive'])

    save_msg(msg, direction="in")

#-------------------------------------------------------------------------------
def update_session():

    session['messages'].append(request.form['Body'])
    session['last_msg_dt'] = to_local(dt=datetime.now())

#-------------------------------------------------------------------------------
def save_msg(text, mobile=None, direction=None):

    number = mobile or session.get('from')
    acct = session.get('account', None)
    d = g.db['alice_chats'].find_one({'mobile':number})

    if not d:
        if not acct:
            log.debug('no account to insert')

        g.db['alice_chats'].insert_one({
            'group':g.group,
            'mobile': number,
            'account': acct,
            'messages': [{
                'timestamp': datetime.utcnow(),
                'message': text,
                'direction': direction
            }],
            'last_message': datetime.utcnow()
        })
    else:
        g.db['alice_chats'].update_one(
            {'mobile': number},
            {
                '$push': {
                    'messages': {
                        'timestamp': datetime.utcnow(),
                        'message': text,
                        'direction': direction
                    }
                },
                '$set': {
                    'group':g.group,
                    'last_message':datetime.utcnow()
                }
           },
           True)

        if not d['account'] and acct:
            g.db['alice_chats'].update_one(
                {'mobile': number},
                {'$set': {'account':acct}}
            )
            log.debug('Added account to chatlog record')

#-------------------------------------------------------------------------------
def archive_chats():
    '''Store all session chats to mongo chatlogs collection.
    '''

    n_stored = 0
    n_updated = 0
    n_alice = 0
    store_keys = ['account', 'from', 'agency', 'messages', 'last_msg_dt']

    #log.debug('saving sessions. total=%s', len(kv_store.keys()))

    for key in current_app.kv_store.keys():
        sess = pickle.loads(current_app.kv_store.get(key))

        if not sess.get('type') == 'alice_chat':
            continue

        n_alice += 1

        r = g.db.chatlogs.update_one(
            {'sess_id':key},
            {'$set': {
                'messages': sess['messages'],
                'last_msg_dt': sess['last_msg_dt']}})

        if r.matched_count == 1:
            n_updated +=1
        elif r.matched_count == 0:
            r = g.db.chatlogs.insert_one({
                'sess_id': key,
                'account': sess.get('account',{}).copy(),
                'messages': sess.get('messages')[:],
                'from': sess.get('from'),
                'agency': sess.get('agency'),
                'last_msg_dt': sess.get('last_msg_dt')})

            n_stored +=1

    log.debug('chat sessions stored (total=%s, stored=%s, updated=%s)',
        n_alice, n_stored, n_updated)

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


