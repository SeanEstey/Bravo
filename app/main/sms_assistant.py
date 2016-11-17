'''app.sms'''

import logging
import twilio
from twilio import twiml
from datetime import datetime, date, time, timedelta
import re
import os
import json
from twilio.rest.lookups import TwilioLookupsClient
from flask import current_app, request, make_response

from app import gsheets
from app import etap
from app.routing import routes
from app import geo
from app import schedule

from app import db

logger = logging.getLogger(__name__)


class EtapError(Exception):
    pass

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

    logger.info(request.cookies)

    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    resp = make_response()
    twml = twiml.Response()

    if not request.cookies.get('etap_id'):
        account = identify_user(resp)

        if not account:
            twml.message(
                "I'm sorry, I can't find an account linked to your phone number. "\
                "Contact recycle@vecova.ca"
            )
            resp.data = str(twml)
            return resp
    else:
        account = etap.call(
          'get_account',
          agency['etapestry'],
          {'account_number':request.cookies['etap_id']},
          silence_exceptions=True)

    msg = request.form['Body']
    from_ = request.form['From']

    if 'SCHEDULE' in msg.upper():
        date = etap.get_udf('Next Pickup Date', account)

        if not date:
            logger.error('missing Next Pickup Date for account %s (SMS: %s)', str(account['id'], from_))

            twml.message("You are not currently scheduled for pickup. Please contact us recycle@vecova.ca")
        else:
            twml.message('Your next pickup is ' + date)
    elif 'PICKUP' in msg.upper():
        pickup_request(resp, twml)
    else:
        name = request.cookies.get('name')

        if not name:
            if account['nameFormat'] == 1: # individual
                name = account['firstName']
            else:
                name = account['name']

        twml.message("Hi %s. Please reply with keyword SCHEDULE if you'd like to know "\
            "your next pickup date." % name)

    resp.data = str(twml)

    return resp

#-------------------------------------------------------------------------------
def pickup_request(resp, twml):
    if msg.upper().find('PICKUP') >= 0:
        logger.info('new pickup request (SMS: %s)', from_)

        db['sms'].update_one(
          {'SmsSid':sms_sid},
          {'$set': { 'awaiting_reply': True, 'request': 'pickup'}})

        send(agency['twilio'], from_,
            "We've received your request. Please \
            reply with your address and postal code")

        return True

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

#-------------------------------------------------------------------------------
def identify_user(resp):
    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    try:
        # Look up number in eTap to see if existing account
        account = etap.call(
          'find_account_by_phone',
          agency['etapestry'],
          {"phone": request.form['From']}
        )
    except Exception as e:
        logger.error("error calling eTap API: %s", str(e))
        raise EtapError('error calling eTap API')

    if not account:
        logger.info('no matching etapestry account found (SMS: %s)',
        request.form['From'])

        return False

    logger.debug(account)

    if account['nameFormat'] == 1: # individual
        name = account['firstName']
    else:
        name = account['name']

    expires=datetime.utcnow() + timedelta(hours=4)

    resp.set_cookie(
        'etap_id',
        value=str(account['id']),
        expires=expires.strftime('%a,%d %b %Y %H:%M:%S GMT'))

    resp.set_cookie(
        'name',
        value=name,
        expires=expires.strftime('%a,%d %b %Y %H:%M:%S GMT'))

    return account


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
