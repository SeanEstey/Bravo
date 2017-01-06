'''app.alice.helper'''

import logging
from flask import request, current_app, g
from datetime import datetime, date, timedelta
from .. import etap, utils, db, bcolors
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get_identity(response):
    '''Per request global flask vars: g.acct_name, g.account, g.agency_conf
    '''

    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    if request.cookies.get('etap_id'):
        account = etap.call(
          'get_account',
          agency['etapestry'],
          {'account_number': request.cookies['etap_id']},
          silence_exceptions=True
        )
        g.acct_name = get_name(account)
        return account

    # New conversation. Try to identify phone number
    try:
        account = etap.call(
          'find_account_by_phone',
          agency['etapestry'],
          {"phone": request.form['From']}
        )
    except Exception as e:
        rfu_task(
            agency['name'],
            'SMS eTap error: "%s"' % str(e),
            name_addy = request.form['From']
        )

        logger.error("eTapestry API: %s", str(e))
        raise EtapError('eTapestry API: %s' % str(e))

    if not account:
        logger.info(
            'no matching etapestry account found (SMS: %s)',
            request.form['From'])

        #rfu_task(
        #    agency['name'],
        #    'No eTapestry account linked to this mobile number. '\
        #    '\nMessage: "%s"' % request.form['Body'],
        #    name_addy='Mobile: %s' % request.form['From'])

        return False

    expires=datetime.utcnow() + timedelta(hours=4)

    g.account = account
    g.acct_name = get_name(account)
    g.agency_conf = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    logger.debug('set g.acct_name: %s', getattr(g, 'acct_name', None))

    set_cookie(response, 'etap_id', account['id'])

    return account

#-------------------------------------------------------------------------------
def get_name(account):
    name = None

    if account['nameFormat'] == 1: # individual
        name = account['firstName']

        # for some reason firstName is sometimes empty even if populated in etap
        if not name:
            name = account['name']
    else:
        name = account['name']

    return name

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
def save_msg(agency):
    msg = get_msg()
    account = getattr(g, 'account', None)

    date_str = date.today().isoformat()

    if not db.alice.find_one({'from':from_,'date':date_str}):
        db.alice.insert_one({
            'agency': agency,
            'account': account,
            'twilio': [request.form.to_dict()],
            'from':from_,
            'date':date.today().isoformat(),
            'last_msg_dt': utils.naive_to_local(datetime.now()),
            'messages':[msg]})
    else:
        db.alice.update_one(
            {'from':from_, 'date': date_str},
            {'$set': {'last_msg_dt': utils.naive_to_local(datetime.now())},
             '$push': {'messages': msg, 'twilio': request.form.to_dict()}})

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
def inc_msg_count(response):
    count = int(get_cookie('messagecount') or 0) + 1
    set_cookie(response, 'messagecount', count)
    return count
