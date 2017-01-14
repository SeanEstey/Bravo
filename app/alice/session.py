'''app.alice.session'''

import logging
from flask import request, current_app, g, request, session
from flask_kvsession import SessionID
from bson.objectid import ObjectId
import cPickle as pickle
from datetime import datetime, date, timedelta
from .. import kv_store, kv_ext, etap, utils, get_db, bcolors
from . import keywords
from .util import related_notific, make_rfu, lookup_acct, event_begun
from .dialog import *
from app.etap import EtapError
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def has_session():
    if session.get('type') == 'alice_chat':
        return True

#-------------------------------------------------------------------------------
def create_session():
    from_ = request.form['From']
    msg = request.form['Body']
    life_duration = current_app.config['PERMANENT_SESSION_LIFETIME']

    # Init session data

    session.permanent = True
    session['type'] = 'alice_chat'
    session['from'] = from_
    session['date'] = date.today().isoformat()
    session['messages'] = [msg]
    session['conf'] = conf = g.db.agencies.find_one({'name':session.get('agency')})
    session['self_name'] = conf['alice']['name']
    session['last_msg_dt'] = utils.naive_to_local(datetime.now())
    session['expiry_dt'] = datetime.now() + life_duration

    try:
        acct = lookup_acct(from_)
    except EtapError as e:
        pass

    if not acct:
        # Unregistered user
        session['anon_id'] = anon_id = str(ObjectId())
        session['valid_kws'] = keywords.anon.keys()

        make_rfu(
            'No eTap acct linked to this mobile number.\nMessage: "%s"' % msg,
            name_addy='Mobile: %s' % from_)

        log.debug('Uregistered user session (anon_id=%s)', anon_id)
    else:
        # Registered user
        session['account'] = acct
        session['valid_kws'] = keywords.user.keys()

        notific = related_notific(log_error=True)

        # Is there a notification user might be replying to?
        if notific:
            session['notific_id'] = notific['_id']
            session['messages'].insert(0, notific['tracking']['body'])
            session['valid_notific_reply'] = not event_begun(notific)

            log.debug('Reply linked to notific_id=%s. valid=%s',
                notific['_id'], session.get('valid_notific_reply'))

        log.debug('Registered user session (etap_id=%s)', acct['id'])

        if not etap.is_active(acct):
            log.error("Acct inactive (etap_id=%s)", acct['id'])
            raise EtapError(dialog['error']['etap']['inactive'])

#-------------------------------------------------------------------------------
def update_session():
    session['messages'].append(request.form['Body'])
    session['last_msg_dt'] = utils.naive_to_local(datetime.now())

#-------------------------------------------------------------------------------
def save_session():
    '''Save session chat from temporary store to db.alice collection
    for views
    '''

    del_keys = [
        '_fresh', '_permanent', 'conf', 'self_name', 'expiry_dt',
        'valid_kws', 'type', 'on_complete']
    n_stored = 0
    n_updated = 0
    n_alice = 0

    log.debug('saving sessions. total=%s', len(kv_store.keys()))

    for key in kv_store.keys():
        sess_doc = pickle.loads(kv_store.get(key))

        if not sess_doc.get('type') == 'alice_chat':
            del_expired_session(sess_doc, key)
            continue

        n_alice += 1

        r = g.db.alice.update_one(
            {'sess_id':key},
            {'$set': {
                'messages': sess_doc['messages'],
                'last_msg_dt': sess_doc['last_msg_dt']}})

        if r.matched_count == 1:
            n_updated +=1
        elif r.matched_count == 0:
            doc = sess_doc.copy()
            doc['sess_id'] = key
            for k in del_keys:
                doc.pop(k, None)
            r = g.db.alice.insert_one(doc)
            n_stored +=1

        del_expired_session(sess_doc, key)

    log.debug(
        'sessions saved (count=%s, stored=%s, updated=%s)',
        n_alice, n_stored, n_updated)

#-------------------------------------------------------------------------------
def del_expired_session(doc, key, force=False):
    m = kv_ext.key_regex.match(key)

    if m:
        sid = SessionID.unserialize(key)
        now = datetime.utcnow()

        lifetime = current_app.config['PERMANENT_SESSION_LIFETIME']

        if force:
            kv_store.delete(key)
            log.debug('sess forced delete (key=%s)', key)
        elif sid.has_expired(lifetime, now):
                log.debug('sess expired. deleted (key=%s)', key)
                kv_store.delete(key)
        else:
            log.debug('sess not yet expired (key=%s)', key)


#-------------------------------------------------------------------------------
def wipe_sessions():
    '''TODO: destroy all sessions
    '''
    return True
