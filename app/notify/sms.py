'''app.notify.sms'''

import logging
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import current_app, render_template
from .. import db
from .. import utils
logger = logging.getLogger(__name__)

# TODO: remove all refs to 'status' outside 'tracking' dict. Redundant
# TODO: write render_template() code to get SMS body

#-------------------------------------------------------------------------------
def add(evnt_id, event_dt, trig_id, acct_id, to, on_send, on_reply):
    '''
    @on_send: {
        'template': 'path/to/template/file'
    }
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

    if to[0:2] != "+1":
        to = "+1" + to

    try:
        client = TwilioRestClient(
            twilio_conf['api_keys']['main']['sid'],
            twilio_conf['api_keys']['main']['auth_id'])
   except twilio.TwilioRestException as e:
        logger.error('SMS not sent. Error getting Twilio REST client. %s', str(e), exc_info=True)
        pass
    
    # TODO: write render_template() code to get SMS body
    
    response = client.messages.create(
        body = ,
        to = to,
        from_ = twilio_conf['sms'],
        status_callback = '%s/notify/sms/delivered' % current_app.config['PUB_URL'])
 

    return response
