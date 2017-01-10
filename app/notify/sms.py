'''app.notify.sms'''

import logging
import json
import os
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from pymongo.collection import ReturnDocument
from flask import current_app, render_template, request
from datetime import datetime, date, time
from .. import db
from .. import utils, html
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
    Output: Twilio response
    '''

    try:
        client = TwilioRestClient(
            twilio_conf['api']['sid'],
            twilio_conf['api']['auth_id'])
    except twilio.TwilioRestException as e:
        logger.error('SMS not sent. Error getting Twilio REST client. %s', str(e), exc_info=True)
        return 'failed'

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

    try:
        msg = client.messages.create(
            body = html.clean_whitespace(body),
            to = notific['to'],
            from_ = from_,
            status_callback = '%s/notify/sms/status' % os.environ.get('BRAVO_HTTP_HOST'))
    except Exception as e:
        error = str(e)
        logger.error('failed to send SMS. %s', str(e))
    else:
        logger.info('queued sms to %s', notific['to'])
        logger.debug(utils.print_vars(msg))
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
def is_reply():
    '''Defined as an incoming msg prior to the notific event datetime'''

    notific = db['notifics'].find_one({
        'to': request.form['From'],
        'type': 'sms',
        'event_dt': {'$gte': datetime.utcnow()},
        'tracking.sent_dt': { '$exists': True }
    })

    if notific:
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def on_reply():
    '''Received reply from user. Invoke handler function.
    Working under request context
    Returns:
        'OK' on success or error string on fail
    '''

    logger.debug('sms.on_reply: %s', request.form.to_dict())

    logger.info('received reply \'%s\' from %s',
        request.form['Body'], request.form['From'])

    # It's a notific reply if from same number as a notific
    # was sent on same date

    notific = db['notifics'].find_one_and_update({
          'to': request.form['From'],
          'type': 'sms',
          'tracking.sent_dt': utils.naive_to_local(datetime.combine(date.today(),time()))
        }, {
          '$set': {
            'tracking.reply': request.form['Body'].upper()
        }},
        return_document=ReturnDocument.AFTER)

    # Import assigned handler module and invoke function
    # to get voice response

    module = __import__(notific['on_reply']['module'], fromlist='.' )

    handler_func = getattr(module, notific['on_reply']['func'])

    response = handler_func(notific)

    return response

#-------------------------------------------------------------------------------
def on_status():
    '''Callback for sending notific SMS
    '''

    logger.info('%s sms to %s', request.form['SmsStatus'], request.form['To'])

    logger.debug('sms.on_status: %s', request.form.to_dict())

    notific = db['notifics'].find_one_and_update({
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

    from .. socketio import socketio_app
    socketio_app.emit('notific_status', {
        'notific_id': str(notific['_id']),
        'status': request.form['SmsStatus'],
        'description': request.form.get('description')})

    return 'OK'
