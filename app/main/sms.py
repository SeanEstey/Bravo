'''app.main.sms'''

import logging
import re
from twilio.rest.lookups import TwilioLookupsClient

from .. import db
from .. import etap

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def enable(agency, accounts):
'''Enable eTap accounts to use Alice'''

    conf = db.agencies.find_one({'name':agency})

    client = TwilioLookupsClient(
      account = conf['twilio']['api']['sid'],
      token = conf['twilio']['api']['auth_id']
    )

    n=0

    for account in accounts:
        # A. Verify Mobile phone setup for SMS
        mobile = etap.get_phone('Mobile', account)

        if mobile:
            # Make sure SMS udf exists

            sms_udf = etap.get_udf('SMS', account)

            if not sms_udf:
                int_format = re.sub(r'[^0-9.]', '', mobile)

                if int_format[0:1] != "1":
                    int_format = "+1" + int_format

                logger.info('Adding SMS field to Account %s', str(account['id']))

                try:
                    etap.call('modify_account', agency['etapestry'], {
                      'id': account['id'],
                      'udf': {'SMS': int_format},
                      'persona': []
                    })
                except Exception as e:
                    logger.error('Error modifying account %s: %s', str(account['id']), str(e))
            # Move onto next account
            continue

        # B. Analyze Voice phone in case it's actually Mobile.
        voice = etap.get_phone('Voice', account)

        if not voice or voice == '':
            continue

        int_format = re.sub(r'[^0-9.]', '', voice)

        if int_format[0:1] != "1":
            int_format = "+1" + int_format

        try:
            info = client.phone_numbers.get(int_format, include_carrier_info=True)
        except Exception as e:
            logger.error('Carrier lookup error (Account %s): %s', str(account['id']), str(e))
            continue

        if info.carrier['type'] != 'mobile':
            continue

        # Found a Mobile number labelled as Voice
        # Update Persona and SMS udf

        logger.info('Acct #%s: Found mobile number. SMS ready.', str(account['id']))

        try:
            etap.call('modify_account', agency['etapestry'], {
              'id': account['id'],
              'udf': {'SMS': info.phone_number},
              'persona': {
                'phones':[
                  {'type':'Mobile', 'number': info.national_format},
                  {'type':'Voice', 'number': info.national_format}
                ]
              }
            })
        except Exception as e:
            logger.error('Error modifying account %s: %s', str(account['id']), str(e))

        n+=1
