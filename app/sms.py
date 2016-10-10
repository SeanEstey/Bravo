import logging
import twilio.twiml
import datetime
import re
from twilio.rest.lookups import TwilioLookupsClient
from flask import current_app

from app import gsheets
from app import etap
from app.routing import routes
from app import geo
from app import schedule

from app import db

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def do_request(to, from_, msg, sms_sid):
    '''Received an incoming SMS message.
    Either initiating a keyword request or replying to conversation.
    Keywords: SCHEDULE, PICKUP
    '''

    agency = db['agencies'].find_one({'twilio.sms' : to})

    # Part of message thread?
    doc = db['sms'].find_one({'awaiting_reply': True, 'From': from_})

    if doc:
        # Msg reply should contain address
        logger.info('Pickup request address: \"%s\" (SMS: %s)', msg, from_)

        block = geo.find_block(msg)

        if not block:
            logger.error('Could not geocode address')

            send(agency['twilio'], from_, 'We could not locate your address')

            return False

        logger.info('Address belongs to Block %s', block)

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

    if msg.upper().find('PICKUP') >= 0:
        logger.info('New pickup request (SMS: %s)', from_)

        db['sms'].update_one(
          {'SmsSid':sms_sid},
          {'$set': { 'awaiting_reply': True, 'request': 'pickup'}})

        send(agency['twilio'], from_,
            "We've received your request. Please \
            reply with your address and postal code")

        return True
    elif msg.upper().find('SCHEDULE') >= 0:
        try:
            # Look up number in eTap to see if existing account
            account = etap.call(
              'find_account_by_phone',
              agency['etapestry'],
              {"phone": from_}
            )
        except Exception as e:
            logger.error("Error calling eTap API: %s", str(e))

        if not account:
            logger.info('No matching etapestry account found (SMS: %s)', from_)
            send(agency['twilio'], from_,
                "Your phone number is not associated with an active account. \
                To update your account, contact us at recycle@vecova.ca")

            return False

        logger.debug(account)

        logger.info('Account %s requested schedule (SMS: %s)', str(account['id']), from_)

        date = etap.get_udf('Next Pickup Date', account)

        if not date:
            logger.error('Missing Next Pickup Date for account %s (SMS: %s)', str(account['id'], from_))

            send(agency['twilio'], from_,
                "You are not currently scheduled for pickup. Please contact us recycle@vecova.ca")

            return False

        send(agency['twilio'], from_, "Your next pickup is " + date)

        return True
    else:
        logger.info('Invalid or missing keyword in msg \"%s\" (SMS: %s)', msg, from_)

        send(agency['twilio'], from_,
            "Invalid keyword. Your request must include either \
            SCHEDULE or PICKUP")

        return False

#-------------------------------------------------------------------------------
def send(twilio_keys, to, msg):
    '''Send an SMS message to recipient
    @agency: mongo document wtih twilio auth info and sms number
    Output: Twilio response
    '''

    if to[0:2] != "+1":
        to = "+1" + to

    try:
        twilio_client = twilio.rest.TwilioRestClient(
          twilio_keys['keys']['main']['sid'],
          twilio_keys['keys']['main']['auth_id']
        )

        response = twilio_client.messages.create(
          body = msg,
          to = to,
          from_ = twilio_keys['sms'],
          status_callback = current_app.config['PUB_URL'] + '/sms/status'
        )
    except twilio.TwilioRestException as e:
        logger.error('sms exception %s', str(e), exc_info=True)

    return response
