'''app.alice.session'''

import logging
from flask import request, current_app, g, request, session
from bson.objectid import ObjectId
import cPickle as pickle
from datetime import datetime, date, timedelta
from .. import kv_store, etap, utils, get_db, bcolors
from app.etap import EtapError
from . import keywords
from .util import related_notific, rfu_task
from .dialog import *
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def has_session():
    if session.get('type') == 'alice_chat':
        return True

#-------------------------------------------------------------------------------
def create_session():
    from_ = request.form['From']
    conf = g.db.agencies.find_one({'twilio.sms.number':request.form['To']})
    life_duration = current_app.config['PERMANENT_SESSION_LIFETIME']

    # Init session data

    session['type'] = 'alice_chat'
    session['from'] = from_
    session['date'] = date.today().isoformat()
    session['messages'] = []
    session['agency'] = conf['name']
    session['conf'] = conf
    session['self_name'] = conf['alice']['name']
    session['expiry_dt'] = datetime.now() + life_duration

    try:
        # Very slow (~750ms-2200ms)
        acct = etap.call(
            'find_account_by_phone',
            conf['etapestry'],
            {'phone': from_})
    except Exception as e:
        rfu_task(conf['name'], 'SMS eTap error "%s"' % str(e),
                 name_addy=request.form['From'])
        log.error('etap api (e=%s)', str(e))
        raise EtapError(dialog['error']['etap']['lookup'])

    if not acct:
        # Unregistered user
        session['anon_id'] = anon_id = str(ObjectId())
        session['valid_kws'] = keywords.anon.keys()

        rfu_task(
            conf['name'],
            'No eTap acctlinked to this mobile number.\n'\
            'Message: "%s"' % get_msg(),
            name_addy='Mobile: %s' % from_)

        log.debug('uregistered user session (anon_id=%s)', anon_id)
    else:
        # Registered user
        session['account'] = acct
        session['valid_kws'] = keywords.user.keys()

        notific = related_notific()

        if notific:
            log.debug('matching notific_id=%s', notific['_id'])
            session['notific_id'] = notific['_id']
            session['messages'] = [notific['tracking']['body']]
            session['valid_notific_reply'] = not event_begun(notific)

        log.debug('registered user session (etap_id=%s)', acct['id'])

        if not etap.is_active(acct):
            log.error("acct inactive (etap_id=%s)", acct['id'])
            raise EtapError(dialog['error']['etap']['inactive'])

#-------------------------------------------------------------------------------
def update_session():
    session['messages'].append(get_msg())
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




