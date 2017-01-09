'''app.alice.helper'''

import logging
from flask import request, current_app, g, request, session
from bson.objectid import ObjectId
from datetime import datetime, date, timedelta
from .. import etap, utils, get_db, bcolors
from . import keywords
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def check_identity():
    '''Unregistered users assigned session['unreg_id']
    '''

    session.permanent = True

    if session.get('account') or session.get('unreg_id'):
        return True

    # Test for unknown registered user

    db = get_db()

    agency = db.agencies.find_one({
        'twilio.sms.number': request.form['To']})

    try:
        # Very slow (~750ms-2200ms)
        session['account'] = etap.call(
            'find_account_by_phone',
            agency['etapestry'],
            {'phone': request.form['From']})
    except Exception as e:
        rfu_task(
            agency['name'],
            'SMS eTap error: "%s"' % str(e),
            name_addy = request.form['From'])

        logger.error("eTapestry API: %s", str(e))

        raise EtapError('eTapestry API: %s' % str(e))
    else:
        if session.get('account'):
            # Known registered user now

            session['self_name'] = agency['alice']['name']
            session['conf'] = agency
            session['valid_kws'] = keywords.user.keys()

            logger.debug(
                'retrieved acct id=%s and agency_conf, saved in session',
                session.get('account')['id'])

            return True

    # Must be unknown unregistered user

    session['self_name'] = agency['alice']['name']
    session['unreg_id'] = str(ObjectId())
    session['conf'] = agency
    session['valid_kws'] = keywords.anon.keys()

    logger.debug(
        'unknown unregistered user. assigning unreg_id="%s"',
        session.get('unreg_id'))

    rfu_task(
        agency['name'],
        'No eTapestry account linked to this mobile number. '\
        '\nMessage: "%s"' % request.form['Body'],
        name_addy='Mobile: %s' % request.form['From'])

    # Known unregistered user now

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
    logger.info('To Alice: %s"%s"%s (%s, count=%s)',
                bcolors.BOLD, request.form['Body'], bcolors.ENDC,
                request.form['From'], get_msg_count())

#-------------------------------------------------------------------------------
def save_msg():
    conf = session.get('conf')

    date_str = date.today().isoformat()

    db = get_db()

    if not db.alice.find_one({'from': request.form['From'],'date':date_str}):
        db.alice.insert_one({
            'agency': conf['name'],
            'account': session.get('account', False),
            'twilio': [request.form.to_dict()],
            'from': request.form['From'],
            'date':date.today().isoformat(),
            'last_msg_dt': utils.naive_to_local(datetime.now()),
            'messages':[request.form['Body']]})
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
