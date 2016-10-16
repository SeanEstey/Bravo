'''app.notify.email'''

import logging
import os
from flask import render_template, current_app, request
from .. import db
from .. import utils, mailgun
logger = logging.getLogger(__name__)

# TODO: remove db['emails'].update op. in app.notify.views.on_delivered just search mid in db['notifics']
# TODO: remove 'status' outside of tracking. Redundant? Replace all refs with 'tracking.status'
# TODO: include date in email subject

#-------------------------------------------------------------------------------
def add(evnt_id, event_dt, trig_id, acct_id, to, on_send, on_reply=None):
    '''
    @on_send: {
        'template': 'path/to/template/file',
        'subject': 'msg'}
    '''

    return db['notifics'].insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': event_dt,
        'on_send': on_send,
        'to': to,
        'type': 'email',
        'tracking': {
            'status': 'pending',
            'mid': None
        }
    }).inserted_id

#-------------------------------------------------------------------------------
def send(notific, mailgun_conf, key='default'):
    '''Private method called by send()
    @key = dict key in email schemas for which template to use
    '''

    # If this is run from a Celery task, it is working outside a request
    # context. Create one so that render_template behaves as if it were in
    # a view function.
    # This template uses url_for() and must require the 'request' variable, which
    # is probably why voice.get_speak() can call render_template() by only
    # creating an application context (without request context)
    with current_app.test_request_context():
        try:
            body = render_template(
                notific['on_send']['template'],
                http_host = os.environ.get('BRAVO_HTTP_HOST'),
                to = notific['to'],
                account = utils.formatter(
                    db['accounts'].find_one({'_id':notific['acct_id']}),
                    to_local_time=True,
                    to_strftime="%A, %B %d",
                    bson_to_json=True
                ),
                evnt_id = notific['evnt_id']
            )
        except Exception as e:
            logger.error('Email not sent because render_template error. %s ', str(e))
            pass

    mid = mailgun.send(
        notific['to'],
        notific['on_send']['subject'],
        body,
        mailgun_conf,
        v={'type':'notific'})

    if mid == False:
        status = 'failed'
    else:
        status = 'queued'

    db['notifics'].update_one({
        '_id':notific['_id']}, {
        '$set': {
            'tracking.status':status,
            'tracking.mid': mid}
        })

    return mid

#-------------------------------------------------------------------------------
def on_delivered():
    '''Called from view webhook. Has request context'''

    logger.info('notification to %s delivered', request.form['recipient'])

    db['notifics'].update_one(
      {'tracking.mid': request.form['Message-Id']},
      {'$set':{
        'tracking.status': request.form['event'],
      }}
    )

    #emit('update_msg', {'id':str(msg['_id']), 'emails': request.form['event']})

#-------------------------------------------------------------------------------
def on_dropped():
    '''Called from view webhook. Has request context'''

    logger.info('notification to %s dropped. %s',
        request.form['recipient'], request.form.get('reason'))

    db['notifics'].update_one(
      {'tracking.mid': request.form['Message-Id']},
      {'$set':{
        'tracking.status': request.form['event'],
      }}
    )

    #emit('update_msg', {'id':str(msg['_id']), 'emails': request.form['event']})
