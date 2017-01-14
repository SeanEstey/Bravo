'''app.notify.sms'''

import logging
import json
import os
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from pymongo.collection import ReturnDocument
from flask import current_app, g, render_template, request
from datetime import datetime, date, time
from .. import get_db, utils, html
import app.alice.outgoing
logger = logging.getLogger(__name__)

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

    db = get_db()

    return db['notifics'].insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': utils.naive_to_local(datetime.combine(event_date, time(8,0))),
        'on_send': on_send,
        'on_reply': on_reply,
        'to': utils.to_intl_format(to),
        'type': 'sms',
        'tracking': {
            'status': 'pending',
            'sid': None,
        }
    }).inserted_id

#-------------------------------------------------------------------------------
def send(notific, twilio_conf):
    '''Send an SMS message to recipient
    @agency: mongo document wtih twilio auth info and sms number

    Returns: twilio compose msg status
    '''

    db = get_db()

    acct = db['accounts'].find_one(
        {'_id': notific['acct_id']})

    # Running via celery worker outside request context
    # Must create one for render_template()
    with current_app.test_request_context():
        try:
            body = render_template(
                'sms/%s/reminder.html' % acct['agency'],
                account = utils.formatter(
                    acct,
                    to_local_time=True,
                    to_strftime="%A, %B %d",
                    bson_to_json=True),
                notific = notific
            )
        except Exception as e:
            logger.error('Error rendering SMS body. %s', str(e))
            return 'failed'

    msg = None
    error = None

    # Prevent sending live msgs if in sandbox
    if os.environ.get('BRAVO_SANDBOX_MODE') == 'True':
        from_ = twilio_conf['sms']['valid_from_number']
    else:
        from_ = twilio_conf['sms']['number']
        logger.info('queued sms to %s', notific['to'])

    body = html.clean_whitespace(body)
    callback = '%s/notify/sms/status' % os.environ.get('BRAVO_HTTP_HOST')

    try:
        msg = app.alice.outgoing.compose(
            body, notific['to'], acct['agency'], twilio_conf,
            status_callback=callback)
    except Exception as e:
        logger.error('compose_msg exc')
    else:
        logger.info('queued sms to %s', notific['to'])
    finally:
        db['notifics'].update_one(
            {'_id': notific['_id']},
            {'$set': {
                'tracking.sid': msg.sid if msg else None,
                'tracking.body': msg.body if msg else None,
                'tracking.error_code': msg.error_code if msg else None,
                'tracking.status': msg.status if msg else 'failed',
                'tracking.descripton': error or None,
            }})

    return msg.status if msg else 'failed'


#-------------------------------------------------------------------------------
def on_status():
    '''Callback for sending notific SMS
    '''

    logger.info('%s sms to %s', request.form['SmsStatus'], request.form['To'])
    logger.debug('sms.on_status: %s', request.form.to_dict())

    notific = g.db.notifics.find_one_and_update({
        'tracking.sid': request.form['SmsSid']}, {
        '$set':{
            'tracking.status': request.form['SmsStatus'],
            'tracking.sent_dt':
            utils.naive_to_local(datetime.combine(date.today(), time()))}
        })

    # Could be a new sid from a reply to reminder text?
    if not notific:
        logger.debug('no notific for sid %s. must be reply.', str(request.form['SmsSid']))
        return 'OK'
        logger.info('rest call')

    from .. socketio import socketio_app
    socketio_app.emit('notific_status', {
        'notific_id': str(notific['_id']),
        'status': request.form['SmsStatus'],
        'description': request.form.get('description')})

    return 'OK'
