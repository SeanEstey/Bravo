import logging
import twilio.twiml
import datetime

from app import app, db, info_handler, error_handler, debug_handler, socketio

from gsheets import create_rfu
import etap

logger = logging.getLogger(__name__)
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
def do_request(to, from_, msg):
    '''Received an incoming SMS message. Process keyword and respond.
    Keywords: SCHEDULE, PICKUP, SIGNUP
    '''

    agency = db['agencies'].find_one({'twilio.sms' : to})

    if agency == None:
        logger.error('No agency found matching SMS number %s', to)
        return False

    # Find keyword

    if msg.upper().find('SIGNUP') >= 0:
        # New signup
        logger.info('Signup request received from ' + from_ + ' via SMS')

        send(agency['twilio'], from_, "We've received your request.")

        return True
    elif msg.upper().find('PICKUP') >= 0:
        # New donor requesting pickup. Try to parse address.
        logger.info(from_ + ' requested a pickup via SMS')

        create_rfu(
          agency['name'],
          'SMS received: \"' + msg + '\"',
          name_address = from_,
          date = datetime.datetime.now().strftime('%-m/%-d/%Y')
        )

        send(agency['twilio'], from_, "Stand by while we schedule you for a pickup")

        return True

    if msg.upper().find('SCHEDULE') == -1:
        logger.info('Invalid or missing sms keyword')

        send(agency['twilio'], from_, "Invalid keyword. Your request must include either \
        SCHEDULE, PICKUP, or SIGNUP")

        return False

    # Keyword == SCHEDULE

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
        logger.error("Error writing to eTap: %s", str(e))

    logger.debug(account)

    if not account:
        logger.error('No etapestry account associated with ' + from_)

        return False

    logger.info('Account ' + str(account['id']) + ' requested next pickup via SMS')

    date = etap.get_udf('Next Pickup Date', account)
    send(agency['twilio'], from_, "Your next pickup is " + date)

    return True


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

        #if e.code == 14101:
          #"To" Attribute is Invalid
          #error_msg = 'number_not_mobile'
        #elif e.code == 30006:
          #erorr_msg = 'landline_unreachable'
        #else:
          #error_msg = e.message

    return response
