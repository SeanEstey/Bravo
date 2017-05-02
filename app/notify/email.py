'''app.notify.email'''
import os
from os import environ as env
from bson.objectid import ObjectId
from flask import g, render_template, current_app, request
from datetime import datetime, date, time
from .. import smart_emit, get_keys
from app.lib import mailgun
from app.lib.utils import formatter
from app.lib.dt import to_utc, ddmmyyyy_to_dt
from app.lib.loggy import Loggy, colors as c
from app.main.donors import get
from app.main.etap import get_udf, NAME_FORMAT
from .utils import simple_dict
log = Loggy('notify.email')

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
        'agency':g.user.agency,
        'nameFormat': name_fmt,
        'udf.status': status})

    if not acct:
        log.error('no scheduled acct to preview (name_format=%s)', name_fmt)
        raise

    path = ''

    if template == 'reminder':
        path = "email/%s/reminder.html" % g.user.agency

    try:
        body = render_template(
            path,
            to = acct['email'],
            account = simple_dict(acct),
            evnt_id = '')
    except Exception as e:
        log.error('template error. desc=%s', str(e))
        log.debug('', exc_info=True)
        raise
    else:
        return body

#-------------------------------------------------------------------------------
def send(notific, mailgun_conf, key='default'):
    '''Private method called by send()
    @key = dict key in email schemas for which template to use
    '''

    acct = g.db.accounts.find_one({'_id':notific['acct_id']})

    try:
        body = render_template(
            notific['on_send']['template'],
            to = notific['to'],
            account = simple_dict(acct),
            evnt_id = notific['evnt_id'])
    except Exception as e:
        log.error('template error. desc=%s', str(e), group=acct['agency'])
        log.debug(str(e), group=acct['agency'])
        raise

    mid = mailgun.send(
        notific['to'],
        notific['on_send']['subject'],
        body,
        mailgun_conf,
        v={'type':'notific'})

    if mid == False:
        log.error('failed to queue %s', notific['to'], group=acct['agency'])
        status = 'failed'
    else:
        log.debug('queued notific to %s', notific['to'], group=acct['agency'])
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

    log.debug('%sdelivered notific to %s%s',
        c.GRN, request.form['recipient'], c.ENDC, group=evnt['agency'])

    smart_emit('notific_status',
        {'notific_id': str(notific['_id']), 'status': request.form['event']})

#-------------------------------------------------------------------------------
def on_dropped():
    '''Called from view webhook. Has request context'''

    notific = g.db.notifics.find_one_and_update(
      {'tracking.mid': request.form['Message-Id']},
      {'$set':{'tracking.status':request.form['event']}})

    evnt = g.db.events.find_one({'_id':notific['evnt_id']})

    log.error('dropped notific to %s', request.form['recipient'], group=evnt['agency'])
    log.debug('reason dropped: %s', request.form.get('reason'), group=evnt['agency'])

    smart_emit('notific_status',
        {'notific_id':str(notific['_id']), 'status':request.form['event']})

    msg = 'notification to %s dropped. %s.' %(
        request.form['recipient'], request.form['reason'])

    agcy = g.db.events.find_one({'_id':notific['evnt_id']})['agency']

    from app.main.tasks import create_rfu
    create_rfu.delay(agcy, msg + request.form.get('description'))
