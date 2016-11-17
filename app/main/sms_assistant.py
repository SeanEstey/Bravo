'''app.sms'''

import logging
import twilio.twiml
import datetime
import re
import os
from twilio.rest.lookups import TwilioLookupsClient
from flask import current_app, request

from app import gsheets
from app import etap
from app.routing import routes
from app import geo
from app import schedule

from app import db

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def is_unsub():
    '''User has unsubscribed all messages from SMS number'''

    unsub_keywords = ['STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT']

    if request.form['Body'].upper() in unsub_keywords:
        logger.info('%s has unsubscribed from this sms number (%s)',
                    request.form['From'], request.form['To'])
        return True

    return False

#-------------------------------------------------------------------------------
def on_receive():
    '''Received an incoming SMS message.
    Either initiating a keyword request or replying to conversation.
    Keywords: SCHEDULE, PICKUP
    '''

    to = request.form['To']
    from_ = request.form['From']
    msg = request.form['Body']
    sms_sid = request.form['SmsStatus']

    logger.info('received sms "%s" (from: %s)', msg, from_)

    agency = db['agencies'].find_one({'twilio.sms.number' : to})

    # Part of message thread?
    doc = db['sms'].find_one({'awaiting_reply': True, 'From': from_})

    if doc:
        # Msg reply should contain address
        logger.info('pickup request address: \"%s\" (SMS: %s)', msg, from_)

        block = geo.find_block(msg)

        if not block:
            logger.error('could not geocode address')

            send(agency['twilio'], from_, 'We could not locate your address')

            return False

        logger.info('address belongs to Block %s', block)

        db['sms'].update_one(doc, {'$set': {'awaiting_reply': False}})

        gsheets.create_rfu(
          agency['name'],
          'Pickup request received (SMS: ' + from_ + ')',
          name_address = msg,
          date = datetime.datetime.now().strftime('%-m/%-d/%Y')
        )

        send(agency['twilio'], from_,
          "Thank you. We'll get back to you shortly with a pickup date")

        return True

    # Check if initiating keyword request

    '''
    if msg.upper().find('PICKUP') >= 0:
        logger.info('new pickup request (SMS: %s)', from_)

        db['sms'].update_one(
          {'SmsSid':sms_sid},
          {'$set': { 'awaiting_reply': True, 'request': 'pickup'}})

        send(agency['twilio'], from_,
            "We've received your request. Please \
            reply with your address and postal code")

        return True
    '''

    try:
        # Look up number in eTap to see if existing account
        account = etap.call(
          'find_account_by_phone',
          agency['etapestry'],
          {"phone": from_}
        )
    except Exception as e:
        logger.error("error calling eTap API: %s", str(e))

    if not account:
        logger.info('no matching etapestry account found (SMS: %s)', from_)
        send(agency['twilio'], from_,
            "Your phone number is not associated with an active account. \
            To update your account, contact us at recycle@vecova.ca")

        return False

    if account['nameFormat'] == 1: # individual
        name = account['firstName']
    else:
        name = account['name']

    if msg.upper().find('SCHEDULE') >= 0:
        logger.info('account %s requested schedule (SMS: %s)', str(account['id']), from_)

        date = etap.get_udf('Next Pickup Date', account)

        if not date:
            logger.error('missing Next Pickup Date for account %s (SMS: %s)', str(account['id'], from_))

            send(agency['twilio'], from_,
                "You are not currently scheduled for pickup. Please contact us recycle@vecova.ca")

            return False

        send(agency['twilio'], from_, "Your next pickup is " + date)

        return True
    else:
        logger.error('invalid sms keyword %s (%s)', msg, from_)

        send(agency['twilio'], from_,
            "Hi %s. Please reply with keyword SCHEDULE if you'd like to know
            your next pickup date." % name)

        return False

#-------------------------------------------------------------------------------
def send(conf, to, msg):
    '''Send an SMS message to recipient
    @agency: mongo document wtih twilio auth info and sms number
    Output: Twilio response
    '''

    if to[0:2] != "+1":
        to = "+1" + to

    try:
        client = twilio.rest.TwilioRestClient(
          conf['api']['sid'],
          conf['api']['auth_id']
        )

        response = client.messages.create(
          body = msg,
          to = to,
          from_ = conf['sms']['number']
          #status_callback = '%s/sms/pickup/status' % os.environ.get('BRAVO_HTTP_HOST')
        )
    except twilio.TwilioRestException as e:
        logger.error('sms exception %s', str(e), exc_info=True)

    return response

#-------------------------------------------------------------------------------
def on_status(args):
    return True
    #    logger.error('Error, SMS status %s', request.form['SmsStatus'])

    # TODO: Move this code into app.sms

    #doc = db['sms'].find_one_and_update(
    #  {'SmsSid': request.form['SmsSid']},
    #  {'$set': { 'SmsStatus': request.form['SmsStatus']}}
    #)

    #if not doc:
    #    db['sms'].insert_one(request.form.to_dict())

    #if request.form['SmsStatus'] == 'received':
    #    sms.do_request(
    #      request.form['To'],
    #      request.form['From'],
    #      request.form['Body'],
    #      request.form['SmsSid'])
