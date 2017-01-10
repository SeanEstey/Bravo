'''app.alice.helper'''

import logging
from flask import request, current_app, g, request, session
from bson.objectid import ObjectId
from datetime import datetime, date, timedelta
from .. import etap, utils, get_db, bcolors
from app.etap import EtapError
from . import keywords
from .dialog import *
log = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def has_session():
    '''
    '''

    if session.get('account') or session.get('anon_id'):
        return True

#-------------------------------------------------------------------------------
def create_session():
    '''
    '''

    session.permanent = True
    db = get_db()
    agency = db.agencies.find_one({'twilio.sms.number': request.form['To']})

    try:
        # Very slow (~750ms-2200ms)
        acct = etap.call(
            'find_account_by_phone',
            agency['etapestry'],
            {'phone': request.form['From']})
    except Exception as e:
        rfu_task(agency['name'], 'SMS eTap error "%s"' % str(e),
                 name_addy=request.form['From'])
        log.error('etap api (e=%s)', str(e))
        raise EtapError(dialog['error']['etap']['lookup'])

    # Unregistered user

    if not acct:
        session['self_name'] = agency['alice']['name']
        session['anon_id'] = anon_id = str(ObjectId())
        session['conf'] = agency
        session['valid_kws'] = keywords.anon.keys()

        log.debug('uregistered user session (anon_id=%s)', anon_id)

        rfu_task(
            agency['name'],
            'No eTapestry account linked to this mobile number. '\
            '\nMessage: "%s"' % request.form['Body'],
            name_addy='Mobile: %s' % request.form['From'])

        return True

    # Registered user. Save session.

    session['account'] = acct
    session['self_name'] = agency['alice']['name']
    session['conf'] = agency
    session['valid_kws'] = keywords.user.keys()

    log.debug('registered user session (etap_id=%s)', acct['id'])

    if not etap.is_active(acct):
        log.error("acct inactive (etap_id=%s)", acct['id'])
        raise EtapError(dialog['error']['etap']['inactive'])

    return True

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

#-------------------------------------------------------------------------------
def log_msg():
    log.info('To Alice: %s"%s"%s (%s, count=%s)',
                bcolors.BOLD, request.form['Body'], bcolors.ENDC,
                request.form['From'], get_msg_count())

#-------------------------------------------------------------------------------
def save_msg():
    conf = session.get('conf')

    date_str = date.today().isoformat()

    db = get_db()

    if not db.alice.find_one({'from': request.form['From'],'date':date_str}):
        r = db.alice.insert_one({
            'agency': conf['name'],
            'account': session.get('account', False),
            'twilio': [request.form.to_dict()],
            'from': request.form['From'],
            'date':date.today().isoformat(),
            'last_msg_dt': utils.naive_to_local(datetime.now()),
            'messages':[request.form['Body']]})

        session['doc_id'] = r.inserted_id
    else:
        db.alice.update_one(
            {'from': request.form['From'], 'date': date_str},
            {'$set': {
                'last_msg_dt': utils.naive_to_local(datetime.now())},
             '$push': {
                'messages': request.form['Body'],
                'twilio': request.form.to_dict()}
            })

#-------------------------------------------------------------------------------
def get_cookie(key):
    return request.cookies.get(key)

#-------------------------------------------------------------------------------
def set_cookie(response, k, v):
    expires=datetime.utcnow() + timedelta(hours=4)
    response.set_cookie(
        k,
        value=str(v),
        expires=expires.strftime('%a,%d %b %Y %H:%M:%S GMT'))

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
