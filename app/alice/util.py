'''app.alice.util'''
import logging
from datetime import date, datetime, timedelta
from flask import g, request, session
from app import get_logger
from app.main.etap import call, EtapError
from app.lib.utils import print_vars
from app.lib.dt import to_local
from .dialog import *
log = get_logger('alice.util')

#-------------------------------------------------------------------------------
def lookup_acct(mobile, agcy):
    try:
        # Very slow (~750ms-2200ms)
        acct = call(
            'find_acct_by_phone',
            session.get('conf')['etapestry'],
            {'phone': mobile})
    except Exception as e:
        raise EtapError(dialog['error']['etap']['lookup'])

    return acct

#-------------------------------------------------------------------------------
def get_chatlogs(start_dt=None):

    if not start_dt:
        start_dt = datetime.utcnow() - timedelta(days=14)

    chats = g.db.chatlogs.find(
        {'agency':g.agency, 'last_msg_dt': {'$gt': start_dt}},
        {'agency':0, '_id':0, 'date':0, 'account':0, 'twilio':0}
    ).sort('last_msg_dt',-1)

    log.debug('chatlogs retrieved, n=%s', chats.count())

    chats = list(chats)
    for chat in chats:
        chat['Date'] = to_local(
            chat.pop('last_msg_dt'),
            to_str='%b %-d @ %-I:%M%p')
        chat['From'] = chat.pop('from')
        chat['Messages'] = chat.pop('messages')

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
