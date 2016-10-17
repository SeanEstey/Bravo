'''app.notify.sms'''

import logging
import os
import re
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import current_app, render_template
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
        'to': to,
        'type': 'sms',
        'tracking': {
            'status': None,
            'sid': None,
        }
    }).inserted_id


#-------------------------------------------------------------------------------
def send(notific, twilio_conf):
    '''Send an SMS message to recipient
    @agency: mongo document wtih twilio auth info and sms number
    Output: Twilio response
    '''

    if notific['to'][0:2] != "+1":
        notific['to'] = "+1" + notific['to']

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
    # Must create one for render_template() and set SERVER_NAME for
    # url_for() to generate absolute URLs
    with current_app.test_request_context():
        #current_app.config['SERVER_NAME'] = os.environ.get('BRAVO_HTTP_HOST')
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
            #current_app.config['SERVER_NAME'] = None
            return False
        #current_app.config['SERVER_NAME'] = None

    # Replace 'from_' with sandbox number
    # Any 'to' is valid with twilio test credentials
    if os.environ.get('BRAVO_TEST_MODE') == 'True':
        from_ = twilio_conf['sms']['valid_from_number']
    else:
        from_ = twilio_conf['sms']['number']

    sms_ = client.messages.create(
        body = html.clean_whitespace(body),
        to = notific['to'],
        from_ = from_,
        status_callback = '%s/notify/sms/status' % os.environ.get('BRAVO_HTTP_HOST'))

    logger.debug(vars(sms_))

    if sms_.status != 'queued':
        logger.error('sms notific failed to send. %s', str(notific['_id']))

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
def on_reply(notific, args):
    '''User has replied to text notific.
    Working under request context
    Invoke handler function to get response.
    Returns: twilio.twiml.Response
    '''

    logger.debug('sms.on_reply: %s', args)

    # Import assigned handler module and invoke function
    # to get voice response

    module = __import__(notific['on_reply']['module'])
    handler_func = getattr(module, notific['on_interact']['func'])

    response = handler_func(notific, args)
    return response

#-------------------------------------------------------------------------------
def on_status(args):
    # do updates
    return True
