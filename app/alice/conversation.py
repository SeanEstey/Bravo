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
        'CONF': conf,
        'MESSAGECOUNT': 0,
        'SELF_NAME': conf['alice']['name']
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
        save_msg(msg, direction="in", user_session=True)
        return

    log.debug('Registered user %s', acct.get('name'))

    session.update({
        'ACCT_ID': acct['id'],
        'ACCOUNT':acct,
        'VALID_KWS': keywords.user.keys()
    })

    # Replying to notification?
    notific = related_notific(log_error=False)
    if notific:
        g.db['notifics'].update_one(
            {'_id':notific['_id']},{'$set':{'tracking.reply':msg}})
        session.update({
            'NOTIFIC_ID': notific['_id'],
            'VALID_NOTIFIC_REPLY': not event_begun(notific)
        })

    if not is_active(acct):
        log.error("Acct inactive (etap_id=%s)", acct['id'])
        raise EtapError(dialog['error']['etap']['inactive'])

    save_msg(msg, direction="in", user_session=True)

    from app.main.socketio import smart_emit
    smart_emit('new_message',
        {'mobile':session['FROM'], 'message':msg}, room=g.get('group'))

    log.info('%s to %s: "%s"',
        session['FROM'][2:], session['SELF_NAME'], request.form['Body'],
        extra={'n_messages': session['MESSAGECOUNT'], 'tag':'sms_msg'})

#-------------------------------------------------------------------------------
def update():
    """MESSAGECOUNT increments only on incoming message.
    """

    # See if there's a more recent eTapestry Account
    msg = request.form['Body']

    save_msg(msg, direction="in", user_session=True)
    session['MESSAGECOUNT'] = session.get('MESSAGECOUNT', 0) + 1

    from app.main.socketio import smart_emit
    smart_emit('new_message',
        {'mobile':session['FROM'], 'message':msg}, room=g.get('group'))

    log.info('%s to %s: "%s"',
        session['FROM'][2:], session['SELF_NAME'], msg,
        extra={'n_messages': session['MESSAGECOUNT'], 'tag':'sms_msg'})

#-------------------------------------------------------------------------------
def toggle_reply_mute(mobile, enabled, minutes=30):

    if enabled:
        until = datetime.utcnow() + timedelta(minutes=minutes)
        g.db['chatlogs'].update_one(
            {'mobile':mobile},
            {'$set':{'mute_replies_until':until}})
        log.debug('Muting replies to %s for %s minutes.', mobile, minutes)
        return 'Auto-reply muted for 5 minutes.'
    else:
        g.db['chatlogs'].update_one(
            {'mobile':mobile},
            {'$unset':{'mute_replies_until':1}})
        log.debug('Unmuting replies to %s', mobile)
        return 'Auto-reply unmuted.'

#-------------------------------------------------------------------------------
def is_muted():

    from app.lib.dt import to_local, local_tz

    doc = g.db['chatlogs'].find_one({'mobile':session['FROM']})

    if doc.get('mute_replies_until'):
        muted_until = to_local(doc['mute_replies_until']).replace(tzinfo = None)

        if datetime.now() < muted_until:
            log.debug('Replies muted until %s.', muted_until.strftime('%H:%M'))
            return True
        else:
            log.debug('Reply mute expired')
            return False
    else:
        return False

#-------------------------------------------------------------------------------
def save_msg(text, mobile=None, acct_id=None, user_session=False, direction=None):
    """@user_session: session only present if conversation is user-initiated
    If saving an outbound msg sent by client, must pass in @mobile
    """

    values = {
        'group':g.group,
        'last_message':datetime.utcnow(),
        'mobile': session['FROM'] if user_session else mobile
    }

    if user_session and session.get('ACCT_ID'):
        values['acct_id'] =  int(session['ACCT_ID'])
    else:
        values['acct_id'] = acct_id

    if direction == 'in':
        values['unread'] = True

    r = g.db['chatlogs'].update_one(
        {'mobile': values['mobile']},
        {'$push': {'messages': {
            'timestamp': datetime.utcnow(),
            'message': text,
            'direction': direction
         }},
         '$set': values
       },
       upsert=True)

    #log.debug('save_msg res=%s', r)

    """if user_session:
        phone = session['FROM']
        acct_id = session.get('ACCT_ID',None)
    else:
        phone = mobile
        acct_id = acct_id
    """

#-------------------------------------------------------------------------------
def no_unread(mobile):

    g.db['chatlogs'].update_one(
        {'mobile': mobile},
        {'$set': {'unread': False}})

#-------------------------------------------------------------------------------
def get_messages(mobile=None, start_dt=None, serialize=True):

    if serialize:
        from app.lib.utils import format_bson

    td = timedelta
    timer = Timer()
    view_days = get_keys('alice')['chatlog_view_days']

    # From single user

    if mobile:
        chat = g.db['chatlogs'].find_one(
            {'group':g.group, 'mobile':mobile},
            {'group':0, '_id':0})

        if chat:
            return format_bson(chat, loc_time=True)
        else:
            return {'mobile':mobile, 'messages':[]}

    # From all users

    now = datetime.utcnow()
    query = {
        'group': g.group,
        'last_message':{
            '$gt': start_dt if start_dt else now-td(days=view_days)
        },
        'messages.direction': {'$in':['in']}
    }
    chats = g.db['chatlogs'].find(query, {'group':0, '_id':0}
        ).limit(50).sort('last_message',-1)

    log.debug('%s chatlogs retrieved. [%s]',
        chats.count(), timer.clock(t='ms'))

    chats = list(chats)

    for chat in chats:
        if not chat.get('acct_id'):
            continue
        acct = g.db['cachedAccounts'].find_one({'group':g.group, 'account.id':chat.get('acct_id')})
        if acct:
            chat['account'] = acct['account']

    if serialize:
        return format_bson(chats, loc_time=True)
    else:
        return chats

#-------------------------------------------------------------------------------
def identify(mobile):

    try:
        acct = call(
            'find_acct_by_phone',
            data={'phone':mobile}, cache=True)
    except Exception as e:
        log.debug('Still no account match for %s', mobile)
    else:
        g.db['chatlogs'].update_one(
            {'mobile':mobile},
            {'$set':{'acct_id':int(acct['id'])}})

        log.debug('Discovered account match. Acct=%s', acct['id'])

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
