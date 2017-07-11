# app.alice.conversation

"""Manage SMS chats between Alice and a user.

Conversation settings held in Flask Sessions. Messages stored
in MongoDB.
"""

import logging, sys
from flask import request, current_app, g, request, session
from bson.objectid import ObjectId
from datetime import datetime, date, timedelta
from app import get_keys
from app.lib.timer import Timer
from app.main.etapestry import is_active, call, get_acct, EtapError
from app.main.tasks import create_rfu
from . import keywords
from .dialog import *
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def exists():
    return True if session.get('TYPE') == 'alice_chat' else False

#-------------------------------------------------------------------------------
def new():
    '''Init session vars after receiving incoming SMS msg'''

    mobile = str(request.form['From'])
    msg = request.form['Body']
    conf = g.db['groups'].find_one({'twilio.sms.number':request.form['To']})
    g.group = conf['name']
    session.permanent = True
    session.update({
        'TYPE': 'alice_chat',
        'FROM': mobile,
        'GROUP': g.group,
        'PAUSE_REPLIES_UNTIL': None,
        'CONF': conf,
        'SELF_NAME': conf['alice']['name'],
        'EXPIRY_DT': datetime.now() + current_app.config['PERMANENT_SESSION_LIFETIME']
    })

    try:
        acct = lookup_acct(mobile)
    except Exception as e:
        log.debug('Uregistered user')
        sys.exc_clear()
        session.update({
            'ANON_ID':  str(ObjectId()),
            'VALID_KWS': keywords.anon.keys()
        })
        save_msg(msg, direction="in")
        return

    log.debug('Registered user %s', acct.get('name'))

    session.update({
        'ACCOUNT':acct,
        'VALID_KWS': keywords.user.keys()
    })

    # Replying to notification?
    notific = related_notific(log_error=False)
    if notific:
        g.db['notifics'].update_one({'_id':notific['_id']},{'$set':{'tracking.reply':msg}})
        session.update({
            'NOTIFIC_ID': notific['_id'],
            'VALID_NOTIFIC_REPLY': not event_begun(notific)
        })

    if not is_active(acct):
        log.error("Acct inactive (etap_id=%s)", acct['id'])
        raise EtapError(dialog['error']['etap']['inactive'])

    save_msg(msg, direction="in")

#-------------------------------------------------------------------------------
def save_msg(text, mobile=None, direction=None):
    '''@mobile: if sending msg outside of session'''

    phone = session.get('FROM', mobile)
    acct = session.get('ACCOUNT', {})

    # TODO: should be able to do upsert here. condense these queries

    if not g.db['chatlogs'].find_one({'mobile':phone}):
        g.db['chatlogs'].insert_one({
            'group':g.group,
            'mobile': phone,
            'acct_id': acct.get('id', None),
            'last_message': datetime.utcnow(),
            'messages': [{
                'timestamp': datetime.utcnow(),
                'message': text,
                'direction': direction
            }]
        })
    else:
        g.db['chatlogs'].update_one(
            {'mobile': phone},
            {'$push': {'messages': {
                'timestamp': datetime.utcnow(),
                'message': text,
                'direction': direction
             }},
             '$set': {
                'acct_id': acct.get('id', None),
                'group':g.group,
                'last_message':datetime.utcnow()
              }
           },
           True)

#-------------------------------------------------------------------------------
def get_messages(start_dt=None, serialize=True):

    timer = Timer()
    view_days = get_keys('alice')['chatlog_view_days']

    if not start_dt:
        start_dt = datetime.utcnow() - timedelta(days=view_days)

    chats = g.db['chatlogs'].find(
        {
            'group': g.group,
            'last_message': {'$gt': start_dt},
            'messages.1': {'$exists': True}
        },
        {'group':0, '_id':0}
    ).limit(50).sort('last_message',-1)

    log.debug('%s chatlogs retrieved. [%s]', chats.count(), timer.clock(t='ms'))

    chats = list(chats)

    for chat in chats:
        chat['account'] = get_acct(chat['acct_id']) if chat.get('acct_id') else None

    if serialize:
        from app.lib.utils import format_bson
        return format_bson(chats, loc_time=True)
    else:
        return chats

#-------------------------------------------------------------------------------
def lookup_acct(mobile):

    try:
        acct = call('find_acct_by_phone', data={'phone': mobile}, cache=True)
    except Exception as e:
        raise EtapError(dialog['error']['etap']['lookup'])
    else:
        return acct

#-------------------------------------------------------------------------------
def related_notific(log_error=False):
    '''Find the most recent db.notifics document for this reply'''

    from_ = request.form['From']

    n = g.db.notifics.find({
        'to': from_,
        'type': 'sms',
        'tracking.status': {'$in': ['sent', 'delivered']},
        'event_dt': {  '$gte': datetime.utcnow() - timedelta(hours=8)}}
    ).sort('tracking.sent_dt', -1).limit(1)

    if n.count() > 0:
        return n.next()
    else:
        if log_error:
            log.debug('notific not found (from=%s)', from_)
        return {}

#-------------------------------------------------------------------------------
def set_notific_reply():
    r = g.db.notifics.update_one(
        {'_id': session.get('NOTIFIC_ID')},
        {'$set': {
            'tracking.reply': request.form['Body']}})

    log.debug('set_notific_reply updated n=%s records', r.modified_count)

#-------------------------------------------------------------------------------
def event_begun(notific):
    if datetime.utcnow() >= notific['event_dt'].replace(tzinfo=None):
        return True
    else:
        return False
