'''app.notify.sms'''

import logging
import json
import os
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import current_app, render_template, request
from datetime import datetime, date, time
from .. import db
from .. import utils, html
logger = logging.getLogger(__name__)

# TODO: remove all refs to 'status' outside 'tracking' dict. Redundant
# TODO: write render_template() code to get SMS body

#-------------------------------------------------------------------------------
def add(evnt_id, event_dt, trig_id, acct_id, to, on_send, on_reply):
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
        'event_dt': event_dt,
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
        pass

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
            return False

    # Prevent sending live msgs if in sandbox
    if os.environ.get('BRAVO_SANDBOX_MODE') == 'True':
        from_ = twilio_conf['sms']['valid_from_number']
    else:
        from_ = twilio_conf['sms']['number']

    sms_ = client.messages.create(
        body = html.clean_whitespace(body),
        to = notific['to'],
        from_ = from_,
        status_callback = '%s/notify/sms/status' % os.environ.get('BRAVO_HTTP_HOST'))

    logger.debug(utils.print_vars(sms_))

    if sms_.status != 'queued':
        logger.info('sms to %s %s', notific['to'], sms_.status)
        logger.error('sms notific failed to send. %s', str(notific['_id']))
    else:
        logger.info('queued sms to %s', notific['to'])

    db['notifics'].update_one(
        {'_id': notific['_id']},
        {'$set': {
            'tracking.sid': sms_.sid,
            'tracking.status': sms_.status,
            'tracking.error_code': sms_.error_code,
            'tracking.body': sms_.body
        }})

    return sms_.status

#-------------------------------------------------------------------------------
def on_reply():
    '''Received reply from user. Invoke handler function.
    Working under request context
    Returns: twilio.twiml.Response
    '''

    logger.info('sms.on_reply: %s', request.form.to_dict())

    # It's a notific reply if from same number as a notific
    # was sent on same date

    notific = db['notifics'].find_one({
        'to': request.form['From'],
        'type': 'sms',
        'tracking.sent_dt':
        utils.naive_to_local(datetime.combine(date.today(),time()))})

    if notific:
        logger.info(utils.formatter(notific))
    else:
        logger.info('reply sms doesnt match any notific sms from today')
        return 'not found'


    # Import assigned handler module and invoke function
    # to get voice response

    module = __import__(notific['on_reply']['module'], fromlist='.' )

    logger.info(utils.print_vars(module))

    handler_func = getattr(module, notific['on_reply']['func'])

    return handler_func(notific)

#-------------------------------------------------------------------------------
def on_status():
    '''Callback for sending notific SMS
    '''

    logger.info('sms.on_status: %s', request.form.to_dict())

    db['notifics'].find_one_and_update({
        'tracking.sid': request.form['SmsSid']}, {
        '$set':{
            'tracking.status': request.form['SmsStatus'],
            'tracking.sent_dt':
            utils.naive_to_local(datetime.combine(date.today(), time()))}
        })
    return True
