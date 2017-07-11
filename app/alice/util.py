# app.alice.util

import logging
from datetime import date, datetime, timedelta
from flask import g, request, session
from app import get_keys
from app.main.etapestry import call, get_acct, EtapError
from app.lib.dt import to_local
from app.lib.timer import Timer
from .dialog import *
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def lookup_acct(mobile):

    try:
        acct = call('find_acct_by_phone', data={'phone': mobile}, cache=True)
    except Exception as e:
        raise EtapError(dialog['error']['etap']['lookup'])
    else:
        return acct

#-------------------------------------------------------------------------------
def get_chatlogs(start_dt=None, serialize=True):

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
        {'_id': session.get('notific_id')},
        {'$set': {
            'tracking.reply': request.form['Body']}})

    log.debug('set_notific_reply updated n=%s records', r.modified_count)

#-------------------------------------------------------------------------------
def event_begun(notific):
    if datetime.utcnow() >= notific['event_dt'].replace(tzinfo=None):
        return True
    else:
        return False
