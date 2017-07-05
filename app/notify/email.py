'''app.notify.email'''
import os
from os import environ as env
from bson.objectid import ObjectId
from flask import g, render_template, current_app, request
from datetime import datetime, date, time
from .. import get_keys, colors as c
from app.lib import mailgun
from app.lib.dt import to_utc, ddmmyyyy_to_dt
from app.main.donors import get
from app.main.etap import get_udf, NAME_FORMAT
from .utils import simple_dict
from logging import getLogger
log = getLogger(__name__)

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
def preview(template, state):
    '''Generate HTML preview
    @template: str from list ['reminder', 'no_pickup']
    @state: str from list ['res_pickup', 'res_drop', 'res_cancel', 'bus_pickup']
    '''

    name_fmt = None
    status = None

    if state == 'bus_pickup':
        status = 'Active'
        name_fmt = NAME_FORMAT['BUSINESS']
    elif state == 'res_pickup':
        status = 'Active'
        name_fmt = NAME_FORMAT['INDIVIDUAL']
    elif state == 'res_drop':
        status = 'Dropoff'
        name_fmt = NAME_FORMAT['INDIVIDUAL']
    elif state == 'res_cancel':
        status = 'Cancelling'
        name_fmt = NAME_FORMAT['INDIVIDUAL']

    acct = g.db.accounts.find_one({
        'agency':g.group,
        'nameFormat': name_fmt,
        'udf.status': status})

    if not acct:
        log.error('no scheduled acct to preview (name_format=%s)', name_fmt)
        raise

    path = ''

    if template == 'reminder':
        path = "email/%s/reminder.html" % g.group

    try:
        body = render_template(path,
            to=acct['email'], account=simple_dict(acct), evnt_id='')
    except Exception as e:
        log.exception('Template error')
        raise
    else:
        return body

#-------------------------------------------------------------------------------
def send(notific, mailgun_conf, key='default'):
    '''Private method called by send()
    @key = dict key in email schemas for which template to use
    '''

    acct = g.db.accounts.find_one({'_id':notific['acct_id']})
    g.group = acct['agency']

    try:
        body = render_template(
            notific['on_send']['template'],
            to = notific['to'],
            account = simple_dict(acct),
            evnt_id = notific['evnt_id'])
    except Exception as e:
        log.exception('Template error')
        raise

    mid = mailgun.send(
        notific['to'],
        notific['on_send']['subject'],
        body,
        mailgun_conf,
        v={'type':'notific'})

    if mid == False:
        log.error('Failed to queue %s', notific['to'])
        status = 'failed'
    else:
        log.debug('Queued notific to %s', notific['to'])
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

    notific = g.db.notifics.find_one_and_update(
      {'tracking.mid': request.form['Message-Id']},
      {'$set':{'tracking.status': request.form['event']}})

    evnt = g.db.events.find_one({'_id':notific['evnt_id']})
    g.group = evnt['agency']

    log.debug('Delivered notific to %s', request.form['recipient'])

    '''smart_emit('notific_status',
        {'notific_id': str(notific['_id']), 'status':
        request.form['event']})'''

#-------------------------------------------------------------------------------
def on_dropped():
    '''Called from view webhook. Has request context'''

    notific = g.db.notifics.find_one_and_update(
      {'tracking.mid': request.form['Message-Id']},
      {'$set':{'tracking.status':request.form['event']}})

    evnt = g.db.events.find_one({'_id':notific['evnt_id']})
    g.group = evnt['agency']

    if not evnt:
        log.error('No event found for dropped notification to %s', request.form['recipient'])

    log.error('Notification failed to send to %s', request.form['recipient'],
        extra={'request':request.form})

    '''smart_emit('notific_status',
        {'notific_id':str(notific['_id']), 'status':request.form['event']})'''

    msg = 'Notification to %s dropped. %s.' %(
        request.form.get('recipient'), request.form.get('reason'))

    from app.main.tasks import create_rfu
    create_rfu.delay(g.group, msg + request.form.get('description',''))
