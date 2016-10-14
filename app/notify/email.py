'''app.notify.email'''

import logging
from flask import render_template, current_app
from .. import db
from .. import utils, mailgun
logger = logging.getLogger(__name__)

# TODO: include date in email subject

#-------------------------------------------------------------------------------
def add(evnt_id, event_dt, trig_id, acct_id, to, on_send, on_reply):
    '''
    @on_send: {
        'template': 'path/to/template/file',
        'subject': 'msg'}
    @on_reply: {
        'module':'module_name',
        'func_name':'handler_func'}
    '''

    return db['notifics'].insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': event_dt,
        'status': 'pending',
        'on_send': on_send,
        'on_reply': on_reply,
        'to': to,
        'type': 'voice',
        'tracking': {
            'status': None,
            'mid': None,
        }
    }).inserted_id

#-------------------------------------------------------------------------------
def send(notific, mailgun_conf, key='default'):
    '''Private method called by send()
    @key = dict key in email schemas for which template to use
    '''

    #template = notific['on_send']['template'][key]

    # If this is run from a Celery task, it is working outside a request
    # context. Create one so that render_template behaves as if it were in
    # a view function.
    # This template uses url_for() and must require the 'request' variable, which
    # is probably why voice.get_speak() can call render_template() by only
    # creating an application context (without request context)
    with current_app.test_request_context():
        # Required for underlying url_for() function in render_template() to
        # generate absolute URL's
        current_app.config['SERVER_NAME'] = current_app.config['PUB_URL']
        try:
            body = render_template(
                notific['template'],
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
            current_app.config['SERVER_NAME'] = None
            pass

        current_app.config['SERVER_NAME'] = None

    mid = mailgun.send(
        notific['to'],
        template['subject'],
        body,
        mailgun_conf)

    if mid == False:
        status = 'failed'
    else:
        status = 'queued'

    db['emails'].insert({
        'agency': db['agencies'].find_one({
            'mailgun.domain':mailgun_conf['domain']})['name'],
        'mid': mid,
        'status': status,
        'type': 'notification',
        'on_status': {}})

    db['notifics'].update_one({
        '_id':notific['_id']}, {
        '$set': {
            'tracking.status':status,
            'tracking.mid': mid}
        })

    return mid

#-------------------------------------------------------------------------------
def on_email_status(webhook):
    '''
    @webhook: webhook args POST'd by mailgun'''

    db['notifics'].update_one(
      {'mid': webhook['Message-Id']},
      {'$set':{
        "status": webhook['event'],
        "code": webhook.get('code'),
        "reason": webhook.get('reason'),
        "error": webhook.get('error')
      }}
    )
