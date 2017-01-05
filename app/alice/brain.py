'''app.alice.brain'''

import logging
import string
import twilio
from twilio import twiml
from datetime import datetime, date, time, timedelta
import re
import os
import json
from twilio.rest.lookups import TwilioLookupsClient
from flask import current_app, request, make_response, g

from .. import etap, utils, gsheets
from app import db, bcolors
from app.booker import geo, search, book

logger = logging.getLogger(__name__)

class EtapError(Exception):
    pass


#-------------------------------------------------------------------------------
def on_receive():
    '''Received an incoming SMS message.
    Cookies saved across requests: 'messagecount', 'awaiting'
    '''

    log_msg()
    msg_count = increment_msg_count()
    response = make_response()

    try:
        account = get_identity(response)
    except Exception as e:
        return send_reply(response, dialog['error']['acct_lookup'])
    else:
        save_msg()

    msg = get_msg()

    if new_convers():
        return handle_new_convers(response, msg)

    if listening_for('keyword'):
        k = find_keyword(msg, get_cookie('listen_kws'))

        if k:
            return handle_keyword(response, k)
        else:
            # TODO: is it another unexpected keyword?
            return False
    elif listening_for('reply'):
        return handle_reply(response)

    return guess_intent(response)

#-------------------------------------------------------------------------------
def guess_intent(response):
    '''Msg sent mid-conversation not understood as keyword or keyword reply.
    Use context clues to guess user intent.
    '''

    # Keep punctuation to get context
    msg = str(request.form['Body']).strip()

    # User asking a question?
    if '?' in msg:
        # TODO: flag msg as important

        return send_reply(
            response,
            dialog['error']['parse_question'] + dialog['user']['options'])

    msg = get_msg()

    # User ending conversation ("thanks")?
    if find_keyword(msg, CONVERSATION_ENDINGS):
        return send_reply(response, dialog['general']['thanks_reply'])

    return default_reply(response)

#-------------------------------------------------------------------------------
def handle_new_conversation(response):
    account = getattr(g, 'account', None)
    msg = str(request.form['Body']).strip()

    k = find_keyword(msg, KEYWORDS)

    if k:
        return handle_keyword(response, k)
    else:
        # Might be a conversation starter, or an unprompted reply
        # Send default reply
        return send_reply(
            get_default_reply(response, account=account),
            response
        )

#-------------------------------------------------------------------------------
def find_keyword(msg, listen_list):
    '''@msg: should be casted to string and stripped()
    '''

    cleaned_msg = msg.upper().translate(None, string.punctuation)
    words = cleaned_msg.split(' ')

    for word in words:
        if word in listen_list:
            return True

    return False

#-------------------------------------------------------------------------------
def get_identity(response):
    '''Per request global flask vars: g.acct_name, g.account, g.agency_conf
    '''

    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    if request.cookies.get('etap_id'):
        account = etap.call(
          'get_account',
          agency['etapestry'],
          {'account_number':request.cookies['etap_id']},
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
def get_msg():
    msg = str(request.form['Body']).strip()
    return msg.upper().translate(None, string.punctuation)

#-------------------------------------------------------------------------------
def handle_keyword(response, k):
    '''Received msg with a keyword command. Send appropriate reply and
    set any necessary listeners.
    '''

    account = getattr(g, 'account', None)

    cmd = commands[k]['on_keyword']

    reply = ''

    # Either call event handler or return dialog for keyword
    if cmd.keys()[0] == 'handler':
        handler_func = getattr(
            cmd['handler']['module'],
            cmd['handler']['func'])

        try:
            reply = handler_func()
        except Exception as e:
            logger.error('%s failed: %s', cmd['handler']['func'], str(e))
            return False
    elif cmd.keys()[0] == 'dialog':
        reply = cmd['dialog']

    # Outcome A (reply with no keywords, clear listeners)
    if not commands[k].get('on_reply'):
        set_cookie(response, 'listen_kws', None)
        set_cookie(response, 'listen_for', None)

        return send_reply(response, reply)

    kw = []
    words = reply.split(' ')

    for word in words:
        if word in commands.keys():
            kw.append(word)

    # Outcome B (reply w/ keywords, listen for them)
    if len(kw) > 0:
        set_cookie(response, 'last_kw', k)
        set_cookie(response, 'listen_for', 'keyword')
        set_cookie(response, 'listen_kws', kw)
    # Outcome C (reply w/o keywords, listen for whole response)
    else:
        set_cookie(response, 'last_kw', k)
        set_cookie(response, 'listen_for', 'reply')
        set_cookie(response, 'listen_kws', None)

    return send_reply(response, reply)

#-------------------------------------------------------------------------------
def handle_reply(response):
    '''Received expected reply. Call event handler for listener key
    '''

    k = get_cookie('last_kw')

    handler_func = getattr(
        commands[k]['on_reply']['handler']['module'],
        commands[k]['on_reply']['handler']['func'])

    try:
        reply = handler_func()
    except Exception as e:
        logger.error('%s failed: %s', k str(e))
        return False

    # clear listeners
    set_cookie(response, 'listen_kws', None)
    set_cookie(response, 'listen_for', None)

    return send_reply(response, reply)

#-------------------------------------------------------------------------------
def listening_for(_type):
    '''@_type: ['keyword', 'reply', None]
    '''

    if get_cookie('listen_for'):
        if get_cookie('listen_for') == _type:
            return True

    return False

#-------------------------------------------------------------------------------
def handle_unregistered(response):
    if request.cookies.get('status') == 'prompt_address':
        rfu_task(
            'vec',
            'Donor at address provided requested '\
            'to register mobile number with their account: %s' % request.form['From'],
            name_addy=request.form['Body'])

        set_cookie(response, 'status', 'address_received')

        return send_reply('Thank you. We\'ll update your account.', response)

    else:
        set_cookie(response, 'status', 'prompt_address')

        return send_reply(STRANGER, response)

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
def new_conversation():
    if get_cookie('messagecount') == 1:
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def tod_greeting():
    '''A simple hello at the beginning of a conversation'''

    hour = datetime.now().time().hour

    tod = ''

    if hour < 12:
        tod = 'morning'
    elif hour >= 12 and hour < 18:
        tod = 'afternoon'
    elif hour >= 18:
        tod = 'evening'

    return 'Good ' + tod + ' '

#-------------------------------------------------------------------------------
def default_reply(response):
    # TODO: Some other unprompted keyword?
    # Can't understand request. Send default reply.
    # TODO: If 3rd time sending default reply, offer assistance

    account = getattr(g, 'account', None)

    msg_count = get_cookie('messagecount')

    if msg_count == 1:
        reply += REPL_INTRO

    reply += REPL_DEFAULT

    return send_reply(reply, response)

#-------------------------------------------------------------------------------
def send_reply(response, dialog):
    '''Add name contexts to beginning of dialog, create TWIML message
    '''

    agency = db.agencies.find_one({
        'twilio.sms.number':request.form['To']})

    if agency['name'] == 'vec':
        ASSISTANT_NAME = 'Alice'
        context = ASSISTANT_NAME + ': '
    else:
        context = ''

    name = getattr(g, 'acct_name', None)
    logger.debug('acct name: %s', name)

    if new_conversation():
        context += get_greeting()

        if name:
            context += ', ' + name + '. '
        else:
            context += '. '
    else:
        if name:
            context += name + ', '
            dialog = dialog[0].lower() + dialog[1:]

    twml = twiml.Response()

    context_dialog = context + dialog

    twml.message(context_dialog)

    logger.info('%s"%s"%s', bcolors.BOLD, context_dialog, bcolors.ENDC)

    response.data = str(twml)

    db.alice.update_one(
        {'from':request.form['From'], 'date': date.today().isoformat()},
        {'$push': {'messages': context_dialog}})

    return response

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
def clear_cookies(response):
    response.set_cookie('name', expires=0)
    response.set_cookie('status', expires=0)
    response.set_cookie('etap_id', expires=0)
    response.set_cookie('agency', expires=0)
    response.set_cookie('messagecount', expires=0)
    return response

#-------------------------------------------------------------------------------
def increment_msg_count(response):
    count = int(get_cookie('messagecount') or 0) + 1
    set_cookie(response, 'messagecount', count)
    return count

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
                bcolors.BOLD, msg, bcolors.ENDC, request.form['From'])

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

