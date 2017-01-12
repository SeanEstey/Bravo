'''app.alice.session'''

import logging
from flask import request, current_app, g, request, session
from bson.objectid import ObjectId
import cPickle as pickle
from datetime import datetime, date, timedelta
from .. import kv_store, etap, utils, get_db, bcolors
from . import keywords
from .util import related_notific, make_rfu, lookup_acct
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

    session['type'] = 'alice_chat'
    session['from'] = from_
    session['date'] = date.today().isoformat()
    session['messages'] = []
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

        notific = related_notific()

        # Is there a notification user might be replying to?
        if notific:
            session['notific_id'] = notific['_id']
            session['messages'] = [notific['tracking']['body']]
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

    for key in kv_store.keys():
        sess_doc = pickle.loads(kv_store.get(key))

        if not sess_doc.get('type') == 'alice_chat':
            continue

        expires = sess_doc['expiry_dt'] - datetime.now()
        log.debug('expires in t=%s', expires)

        r = g.db.alice.update_one(
            {'sess_id':key},
            {'$set': {
                'messages': sess_doc['messages'],
                'last_msg_dt': sess_doc['last_msg_dt']}})

        if r.matched_count == 1:
            log.debug(
                'updated stored session, n=%s', r.modified_count)
        elif r.matched_count == 0:
            new_doc = sess_doc.copy()
            new_doc['sess_id'] = key
            r = g.db.alice.insert_one(new_doc)
            log.debug('stored session, id=%s', r.inserted_id)

#-------------------------------------------------------------------------------
def wipe_sessions():
    '''TODO: destroy all sessions
    '''
    return True




