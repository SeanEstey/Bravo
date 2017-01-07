'''app.alice.helper'''

import logging
from flask import request, current_app, g, request, session
from bson.objectid import ObjectId
from datetime import datetime, date, timedelta
from .. import etap, utils, db, bcolors
from . import conf
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def check_identity():
    '''Unregistered users assigned session['unreg_id']
    '''

    session.permanent = True

    if session.get('account') or session.get('unreg_id'):
        return True

    # Test for unknown registered user

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

            session['conf'] = agency
            session['valid_kws'] = conf.user_keywords

            logger.debug(
                'retrieved acct id=%s and agency_conf, saved in session',
                session.get('account')['id'])

            return True

    # Must be unknown unregistered user

    session['unreg_id'] = str(ObjectId())
    session['conf'] = agency
    session['valid_kws'] = conf.anon_keywords

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
def get_name():
    '''Returns account 'name' or 'firstName' for registered users,
    None for unregistered users'''

    if not session.get('account'):
        return False

    account = session.get('account')

    nf = account['nameFormat']

    # Formats: None (0), Family (2), Business (2)
    if nf == 0 or nf == 2 or nf == 3:
        return account['name']

    # Format: Individual (1)

    if account['firstName']:
        return account['firstName']
    else:
        return account['name']

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
    logger.debug(request.form.to_dict())

    logger.info('To Alice: %s"%s"%s (%s)',
                bcolors.BOLD, request.form['Body'], bcolors.ENDC, request.form['From'])

#-------------------------------------------------------------------------------
def save_msg():
    conf = session.get('conf')

    date_str = date.today().isoformat()

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
def inc_msg_count():

    count = session.get('messagecount', 0) + 1
    session['messagecount'] = count

    #count = int(get_cookie('messagecount') or 0) + 1
    #set_cookie(response, 'messagecount', count)
    #return count

#-------------------------------------------------------------------------------
def check_store_for_account():
    # Old way of obtaining identity
    '''
    account = db.alice.find_one({
        'from': request.form['From'],
        'date': date.today().isoformat()
    }).get('account')

    '''


    # store _id is user's phone in +14031234567 format
    if not request.form['From'] in store.keys():
        logger.debug('no store created for account. creating now')

        account = etap.call(
          'find_account_by_phone',
          agency['etapestry'],
          {'phone': request.form['From']}
        )

        store.put(request.form['From'], account)
    else:
        account = store.get(request.form['From'])

        logger.debug('account id %s retrieved from saved store.', account['id'])
    return True
