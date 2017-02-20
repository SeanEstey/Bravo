'''app.notify.email'''
import logging, os
from os import environ as env
from flask import g, render_template, current_app, request
from datetime import datetime, date, time
from .. import get_logger, smart_emit, get_keys
from app.lib import mailgun
from app.lib.utils import formatter
from app.lib.dt import to_utc
from app.lib.logger import colors as c
log = get_logger('notify.email')

#-------------------------------------------------------------------------------
def add(evnt_id, event_date, trig_id, acct_id, to, on_send, on_reply=None):
    '''@on_send: {
        'template': 'path/to/template/file',
        'subject': 'msg'}
    '''

    return g.db.notifics.insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': to_utc(d=event_date, t=time(8,0)),
        'on_send': on_send,
        'to': to,
        'type': 'email',
        'tracking': {
            'status': 'pending',
            'mid': None}}).inserted_id

#-------------------------------------------------------------------------------
def send(notific, mailgun_conf, key='default'):
    '''Private method called by send()
    @key = dict key in email schemas for which template to use
    '''

    try:
        body = render_template(
            notific['on_send']['template'],
            to = notific['to'],
            account = formatter(
                g.db.accounts.find_one({'_id':notific['acct_id']}),
                to_local_time=True,
                to_strftime="%A, %B %d",
                bson_to_json=True),
            evnt_id = notific['evnt_id'])
    except Exception as e:
        log.error('template error. desc=%s', str(e))
        log.debug('', exc_info=True)
        raise

    mid = mailgun.send(
        notific['to'],
        notific['on_send']['subject'],
        body,
        mailgun_conf,
        v={'type':'notific'})

    if mid == False:
        log.error('failed to queue %s', notific['to'])
        status = 'failed'
    else:
        log.debug('queued notific to %s', notific['to'])
        status = 'queued'

    g.db.notifics.update_one({
        '_id':notific['_id']}, {
        '$set': {
            'tracking.status':status,
            'tracking.mid': mid}})

    return status

#-------------------------------------------------------------------------------
def on_delivered():
    '''Called from view webhook. Has request context'''

    log.debug('%sdelivered notific to %s%s', c.GRN, request.form['recipient'], c.ENDC)

    notific = g.db.notifics.find_one_and_update(
      {'tracking.mid': request.form['Message-Id']},
      {'$set':{'tracking.status': request.form['event']}})

    smart_emit('notific_status',
        {'notific_id': str(notific['_id']), 'status': request.form['event']})

#-------------------------------------------------------------------------------
def on_dropped():
    '''Called from view webhook. Has request context'''

    log.error('dropped notific to %s', request.form['recipient'])
    log.debug('reason dropped: %s', request.form.get('reason'))

    notific = g.db.notifics.find_one_and_update(
      {'tracking.mid': request.form['Message-Id']},
      {'$set':{'tracking.status':request.form['event']}})

    smart_emit('notific_status',
        {'notific_id':str(notific['_id']), 'status':request.form['event']})

    msg = 'receipt to %s dropped. %s.' %(
        request.form['recipient'], request.form['reason'])

    agcy = g.db.notific_events.find_one({'_id':notific['evnt_id']})['agency']

    from app.main.tasks import create_rfu
    create_rfu.delay(
        agcy, msg + request.form.get('description'),
        options={
            'Date': date.today().strftime('%-m/%-d/%Y')})
