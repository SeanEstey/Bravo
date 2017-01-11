'''app.alice.helper'''

import logging
from flask import request, current_app, g, request, session
from bson.objectid import ObjectId
import cPickle as pickle
from datetime import datetime, date, timedelta
from .. import kv_store, etap, utils, get_db, bcolors
from app.etap import EtapError
from . import keywords
from .dialog import *
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def has_session():
    if session.get('alice'): 
        return True

#-------------------------------------------------------------------------------
def create_session():
    ''''''

    db = get_db()
    from_ = request.form['From']
    conf = db.agencies.find_one({'twilio.sms.number': request.form['To']})

    # Init session data

    session['alice'] = True
    session['expiry_dt'] = \
        datetime.now() + current_app.config['PERMANENT_SESSION_LIFETIME']
    session['messages'] = []
    session['agency'] = conf['name']
    session['self_name'] = conf['alice']['name']
    session['from'] = from_
    session['date'] = date.today().isoformat()

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

        log.debug('registered user session (etap_id=%s)', acct['id'])

        if not etap.is_active(acct):
            log.error("acct inactive (etap_id=%s)", acct['id'])
            raise EtapError(dialog['error']['etap']['inactive'])

#-------------------------------------------------------------------------------
def update_session():
    session['messages'].append(get_msg())
    session['last_msg_dt'] = utils.naive_to_local(datetime.now())

#-------------------------------------------------------------------------------
def get_msg():
    '''Convert from unicode to prevent weird parsing issues'''
    return str(request.form['Body']).strip()

#-------------------------------------------------------------------------------
def log_msg():
    log.info('To Alice: %s"%s"%s (%s, count=%s)',
                bcolors.BOLD, request.form['Body'], bcolors.ENDC,
                request.form['From'], get_msg_count())

#-------------------------------------------------------------------------------
def is_notific_reply():
    if get_msg_count() > 1:
        conv_id = session.get('conv_id')
        conv = db.alice.find_one({'_id':conv_id})

        return conv.get('notific_id')
    else:
        notific = get_recent_notific()

        if not notific or event_begun(notific):
            return False

        return notific

#-------------------------------------------------------------------------------
def related_notific(log_error=False):
    '''Find the most recent db.notifics document for this reply'''

    from_ = request.form['From']
    db = get_db()

    n = db.notifics.find({
        'to': from_,
        'type': 'sms',
        'tracking.status': 'delivered',
        'event_dt': {  '$gte': datetime.utcnow()}}
    ).sort('tracking.sent_dt', -1).limit(1)

    if n.count() > 0:
        return n.next()
    else:
        if log_error:
            log.error('notific not found (from=%s)', from_)
        return {}

#-------------------------------------------------------------------------------
def event_begun(notific):
    if datetime.utcnow() >= notific['event_dt'].replace(tzinfo=None):
        log.error('route already built (etap_id=%s)', session.get('account')['id'])
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def get_chatlogs(agency, start_dt=None):

    if not start_dt:
        start_dt = datetime.utcnow() - timedelta(days=14)

    # double-check start_dt arg is UTC

    db = get_db()

    chats = db.alice.find(
        {'agency':agency, 'last_msg_dt': {'$gt': start_dt}},
        {'agency':0, '_id':0, 'date':0, 'account':0, 'twilio':0}
    ).sort('last_msg_dt',-1)

    chats = list(chats)
    for chat in chats:
        chat['Date'] =  utils.tz_utc_to_local(
            chat.pop('last_msg_dt')
        ).strftime('%b %-d @ %-I:%M%p')
        chat['From'] = chat.pop('from')
        chat['Messages'] = chat.pop('messages')

    return chats

#-------------------------------------------------------------------------------
def get_msg_count():
    return session.get('messagecount')

#-------------------------------------------------------------------------------
def inc_msg_count():
    '''Track number of received messages in conversation'''

    session['messagecount'] = session.get('messagecount', 0) + 1

#-------------------------------------------------------------------------------
def wipe_sessions():
    '''TODO: destroy all sessions
    '''
    return True

#-------------------------------------------------------------------------------
def save_conversations():
    db = get_db()

    for key in kv_store.keys():
        sess_doc = pickle.loads(kv_store.get(key))

        if not sess_doc.get('alice'):
            continue

        expires = sess_doc['expiry_dt'] - datetime.now()
        log.debug('expires in t=%s', expires)

        r = db.alice.update_one(
            {'sess_id':key},
            {'$set': {
                'messages': sess_doc['messages'],
                'last_msg_dt': sess_doc['last_msg_dt']}})

        if r.matched_count == 1:
            log.debug(
                'updated session, n_matched=%s, n_mod=%s',
                r.matched_count, r.modified_count)
        elif r.matched_count == 0:
            new_doc = sess_doc.copy()
            new_doc['sess_id'] = key
            r = db.alice.insert_one(new_doc)
            log.debug('saved new session, id=%s', r.inserted_id)

#-------------------------------------------------------------------------------
def rfu_task(agency, note,
             a_id=None, npu=None, block=None, name_addy=None):

    from .. import tasks
    tasks.rfu.apply_async(
        args=[
            agency,
            note
        ],
        kwargs={
            'a_id': a_id,
            'npu': npu,
            'block': block,
            '_date': date.today().strftime('%-m/%-d/%Y'),
            'name_addy': name_addy
        },
        queue=current_app.config['DB'])
