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
    msg = request.form['Body']
    from_ = request.form['From']
    resp = make_response()
    account = None
    greeting = ''

    expires=datetime.utcnow() + timedelta(hours=4)
    resp.set_cookie(
        'messagecount',
        value=str(int(request.cookies.get('messagecount', 0))+1),
        expires=expires.strftime('%a,%d %b %Y %H:%M:%S GMT'))

    account = get_identity(resp)

    if not account:
        return send_reply(
            "I'm sorry, I can't find an account linked to your phone number. "\
            "Contact recycle@vecova.ca",
            resp
        )

    if new_conversation():
        greeting = get_greeting(account)

    # Keyword handler
    if 'SCHEDULE' in msg.upper():
        if not etap.get_udf('Next Pickup Date', account):
            logger.error(
                'missing Next Pickup Date for account %s (SMS: %s)',
                str(account['id'], from_))

            return send_reply(
                "You are not currently scheduled for pickup. "\
                "Please contact us recycle@vecova.ca",
                resp
            )

        npu_dt = etap.ddmmyyyy_to_dt(etap.get_udf('Next Pickup Date', account))
        npu_str = npu_dt.strftime('%A, %B %-d')

        return send_reply(
            greeting + 'Your next pickup is scheduled on ' + npu_str,
            resp
        )
    # No keyword.
    else:
        return send_reply(
            greeting + get_help_reply(resp, account=account),
            resp
        )

#-------------------------------------------------------------------------------
def new_conversation():
    if int(request.cookies.get('messagecount', 0)) == 0:
        return True
    else:
        return False

#-------------------------------------------------------------------------------
def get_greeting(account=None):
    '''A simple hello at the beginning of a conversation'''

    greeting = 'Good ' + get_tod()

    if account:
        if account['nameFormat'] == 1: # individual
            name = account['firstName']
        else:
            name = account['name']

        greeting += ', ' + name + '. '
    else:
        greeting += '. '

    return greeting

#-------------------------------------------------------------------------------
def get_help_reply(resp, account=None):
    reply = ''

    messagecount = int(request.cookies.get('messagecount', 0))

    if messagecount == 0:
        reply += 'How can I help you today? '

    reply += 'If you reply with the word "schedule" I can tell you your '\
             'next pickup date'

    return reply

#-------------------------------------------------------------------------------
def send_reply(msg, resp):
    twml = twiml.Response()
    twml.message(msg)
    resp.data = str(twml)
    return resp

#-------------------------------------------------------------------------------
def get_tod():
    hour = datetime.now().time().hour

    if hour < 12:
        return 'morning'
    elif hour >= 12 and hour < 18:
        return 'afternoon'
    elif hour >= 18:
        return 'evening'

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
def get_identity(resp):
    agency = db.agencies.find_one({'twilio.sms.number':request.form['To']})

    if request.cookies.get('etap_id'):
        return etap.call(
          'get_account',
          agency['etapestry'],
          {'account_number':request.cookies['etap_id']},
          silence_exceptions=True
        )

    # New conversation. Try to identify phone number
    try:
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
