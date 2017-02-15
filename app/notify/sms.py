'''app.notify.sms'''
import logging, json, os
from os import environ as env
from flask import current_app, g, render_template, request
from datetime import datetime, date, time
from .. import get_logger, smart_emit, get_keys, utils, html
from app.dt import to_utc, to_local
from app.logger import colors as c
from app.alice.outgoing import compose
log = get_logger('notify.sms')

#-------------------------------------------------------------------------------
def add(evnt_id, event_date, trig_id, acct_id, to, on_send, on_reply):
    '''
    @on_send: {
        'template': 'path/to/template/file'
    }

    I think I need to register Twilio 'app_sid' to receive text replies

    @on_reply: {
        'module':'module_name',
        'func':'handler_func'}
    '''

    return g.db.notifics.insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': to_utc(d=event_date, t=time(8,0)),
        'on_send': on_send,
        'on_reply': on_reply,
        'to': utils.to_intl_format(to),
        'type': 'sms',
        'tracking': {
            'status': 'pending',
            'sid': None}}).inserted_id

#-------------------------------------------------------------------------------
def send(notific, twilio_conf):
    '''Called from celery task. Send an SMS message to recipient
    @agency: mongo document wtih twilio auth info and sms number
    Returns: twilio compose msg status
    '''

    acct = g.db.accounts.find_one({'_id': notific['acct_id']})

    try:
        body = render_template(
            'sms/%s/reminder.html' % acct['agency'],
            account = utils.formatter(
                acct,
                to_local_time=True,
                to_strftime="%A, %B %d",
                bson_to_json=True),
            notific = notific)
    except Exception as e:
        log.error('Error rendering SMS body. %s', str(e))
        return 'failed'

    msg = None
    error = None

    # Prevent sending live msgs if in sandbox
    if env['BRV_SANDBOX'] == 'True':
        from_ = twilio_conf['sms']['valid_from_number']
    else:
        from_ = twilio_conf['sms']['number']
        log.debug('queued sms to %s', notific['to'])

    body = html.clean_whitespace(body)
    http_host = env['BRV_HTTP_HOST']
    http_host = http_host.replace('https','http') if http_host.find('https') == 0 else http_host
    callback = '%s/notify/sms/status' % http_host

    try:
        msg = compose(acct['agency'], body, notific['to'], callback=callback)
    except Exception as e:
        log.error('error queuing SMS, desc="%s"', str(e))
        log.debug('', exc_info=True)
    #else:
    #    log.debug('queued SMS to %s', notific['to'])
    finally:
        g.db.notifics.update_one(
            {'_id': notific['_id']},
            {'$set': {
                'tracking.sid': msg.sid if msg else None,
                'tracking.body': msg.body if msg else None,
                'tracking.error_code': msg.error_code if msg else None,
                'tracking.status': msg.status if msg else 'failed',
                'tracking.descripton': error or None}})

    return msg.status if msg else 'failed'


#-------------------------------------------------------------------------------
def on_status():
    '''Callback for sending notific SMS
    '''

    status = request.form['SmsStatus']
    to = request.form['To']

    if status == 'delivered':
        log.debug('%sdelivered SMS notific to %s%s', c.GRN, to, c.ENDC)
    elif status == 'queued':
        log.debug('queued SMS notific to %s', to)
    else:
        log.debug('%s SMS notific to %s', status, to)

    notific = g.db.notifics.find_one_and_update({
        'tracking.sid': request.form['SmsSid']}, {
        '$set':{
            'tracking.status': status,
            'tracking.sent_dt': to_local(dt=datetime.now())}})

    # Could be a new sid from a reply to reminder text?
    if not notific:
        log.debug('no notific for sid %s. must be reply.', str(request.form['SmsSid']))
        return 'OK'
        log.info('rest call')

    smart_emit('notific_status', {
        'notific_id': str(notific['_id']),
        'status': request.form['SmsStatus'],
        'description': request.form.get('description')})

    return 'OK'
