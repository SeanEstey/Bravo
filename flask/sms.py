import logging
import twilio.twiml
import datetime
import re
from twilio.rest.lookups import TwilioLookupsClient

from app import app,db,info_handler,error_handler,debug_handler,socketio
from tasks import celery_app

from gsheets import create_rfu
import etap
import routing
from scheduler import get_accounts

logger = logging.getLogger(__name__)
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)


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

        geocoded_address = routing.geocode(msg)

        if not geocoded_address:
            logger.error('Could not geocode address')

            send(agency['twilio'], from_, 'We could not locate your address')

            return False

        db['sms'].update_one(doc, {'$set': {'awaiting_reply': False}})

        create_rfu(
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
        # Look up number in eTap to see if existing account
        keys = {'user':agency['etapestry']['user'], 'pw':agency['etapestry']['pw'],
                'agency':agency['name'],'endpoint':app.config['ETAPESTRY_ENDPOINT']}
        try:
            account = etap.call(
              'find_account_by_phone',
              keys,
              {"phone": from_}
            )
        except Exception as e:
            logger.error("Error calling eTap API: %s", str(e))

        if not account:
            logger.error('No matching etapestry account found (SMS: %s)', from_)

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
          status_callback = app.config['PUB_URL'] + '/sms/status'
        )
    except twilio.TwilioRestException as e:
        logger.error('sms exception %s', str(e), exc_info=True)

    return response

#-------------------------------------------------------------------------------
@celery_app.task
def verify_sms_status():
    # Verify that all accounts in upcoming residential routes with mobile
    # numbers are set up to interact with Bravo SMS system

    agency_name = 'vec'

    agency_settings = db['agencies'].find_one({'name':agency_name})

    agency_settings['twilio']['keys']['main']['auth_id']

    # Get accounts scheduled on Residential routes 3 days from now
    accounts = get_accounts(
        agency_settings['etapestry'],
        agency_settings['cal_ids']['res'],
        agency_settings['oauth'],
        days_from_now=3)

    if len(accounts) < 1:
        return False

    etap_auth_keys = {
      'user':agency_settings['etapestry']['user'],
      'pw':agency_settings['etapestry']['pw'],
      'agency':agency_name,
      'endpoint':app.config['ETAPESTRY_ENDPOINT']
    }

    for account in accounts:
        # A. Verify Mobile phone setup for SMS
        mobile = etap.get_phone('Mobile', account)

        if mobile:
            # Make sure SMS udf exists

            sms_udf = etap.get_udf('SMS', account)

            if not sms_udf:
                international_format = re.sub(r'\-|\(|\)|\s', '', mobile['number'])

                if international_format[0:2] != "+1":
                    international_format = "+1" + international_format

                logger.info('Account %s has Mobile number but missing SMS udf. Updating', str(account['id']))

                try:
                    etap.call('modify_account', etap_auth_keys, {
                      'id': account['id'],
                      'udf': {'SMS': international_format},
                      'persona': []
                    })
                except Exception as e:
                    logger.error('Error modifying account %s: %s', str(account['id']), str(e))
            # Move onto next account
            continue

        # B. Analyze Voice phone in case it's actually Mobile.
        voice = etap.get_phone('Voice', account)

        if not voice:
            continue

        try:
            client = TwilioLookupsClient(
              account = agency_settings['twilio']['keys']['main']['sid'],
              token = agency_settings['twilio']['keys']['main']['auth_id']
            )

            international_format = '+1' + re.sub(r'\-|\(|\)|\s', '', voice['number'])
            info = client.phone_numbers.get(international_format, include_carrier_info=True)
        except Exception as e:
            logger.error('Carrier lookup error on Account %s: %s',
                    str(account['id']), str(e))
            continue

        if info.carrier['type'] != 'mobile':
            continue

        # Found a Mobile number labelled as Voice
        # Update Persona and SMS udf

        logger.info('Account %s had mobile number mislabelled. Updating Mobile persona and SMS udf', str(account['id']))

        try:
            etap.call('modify_account', etap_auth_keys, {
              'id': account['id'],
              'udf': {'SMS': info.phone_number},
              'persona': {
                  'phones':{
                      'type':'Mobile',
                      'number': info.national_format
                  }
              }
            })
        except Exception as e:
            logger.error('Error modifying account %s: %s', str(account['id']), str(e))

    return True
