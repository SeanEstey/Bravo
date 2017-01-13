'''app.alice.util'''

import logging
from datetime import date, datetime, timedelta
from flask import g, request, session
from .. import etap
from app.etap import EtapError
from .dialog import *
from app.utils import tz_utc_to_local
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def lookup_acct(mobile):
    try:
        # Very slow (~750ms-2200ms)
        acct = etap.call(
            'find_account_by_phone',
            session.get('conf')['etapestry'],
            {'phone': mobile}
        )
    except Exception as e:
        log.error('etap api (e=%s)', str(e))

        make_rfu(
            'SMS eTap error "%s"' % str(e),
            name_addy= session.get('from'))

        raise EtapError(dialog['error']['etap']['lookup'])

    return acct

#-------------------------------------------------------------------------------
def get_chatlogs(start_dt=None):

    if not start_dt:
        start_dt = datetime.utcnow() - timedelta(days=14)

    chats = g.db.alice.find(
        {'agency':g.agency, 'last_msg_dt': {'$gt': start_dt}},
        {'agency':0, '_id':0, 'date':0, 'account':0, 'twilio':0}
    ).sort('last_msg_dt',-1)

    log.debug('chatlogs retrieved, n=%s', chats.count())

    chats = list(chats)
    for chat in chats:
        chat['Date'] =  tz_utc_to_local(
            chat.pop('last_msg_dt')
        ).strftime('%b %-d @ %-I:%M%p')
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

#-------------------------------------------------------------------------------
def make_rfu(note, a_id=None, npu=None, block=None, name_addy=None):

    from .. import tasks
    tasks.rfu.apply_async(
        args=[session.get('agency'), note],
        kwargs={
            'a_id': a_id,
            'npu': npu,
            'block': block,
            '_date': date.today().strftime('%-m/%-d/%Y'),
            'name_addy': name_addy
        },
        queue=g.db.db_name)
