'''app.booker.book'''

import logging
import os
from flask import render_template, request

from .. import etap
from .. import mailgun
from .. import db

logger = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def make(agency, aid, block, date_str, driver_notes, name, email, confirmation):
    '''Makes the booking in eTapestry by posting to Bravo.
    This function is invoked from the booker client.
    @aid: eTap account id
    @date_str: native etap format dd/mm/yyyy
    '''

    logger.info('Booking account %s for %s', aid, date_str)

    conf = db.agencies.find_one({'name':agency})

    try:
        response = etap.call(
          'make_booking',
          conf['etapestry'],
          data={
            'account_num': int(aid),
            'type': 'pickup',
            'udf': {
                'Driver Notes': '***' + driver_notes + '***',
                'Office Notes': '***RMV ' + block + '***',
                'Block': block,
                'Next Pickup Date': date_str
            }
          }
        )
    except EtapError as e:
        return {
            'status': 'failed',
            'description': 'etapestry error: %s' % str(e)
        }
    except Exception as e:
        logger.error('failed to book: %s', str(e))
        return {
            'status': 'failed',
            'description': str(e)
        }

    if confirmation:
        send_confirmation(agency, email, aid, name, date_str)

    return {
        'status': 'success',
        'description': response
    }

#-------------------------------------------------------------------------------
def send_confirmation(agency, to, aid, name, date_str):
    try:
        body = render_template(
            'email/%s/confirmation.html' % agency,
            http_host = os.environ.get('BRAVO_HTTP_HOST'),
            to = to,
            name = name,
            date_str = etap.ddmmyyyy_to_dt(date_str).strftime('%B %-d %Y')
        )
    except Exception as e:
        logger.error('Email not sent because render_template error. %s ', str(e))
        pass

    conf = db.agencies.find_one({'name':agency})

    mid = mailgun.send(
        to,
        'Pickup Confirmation',
        body,
        conf['mailgun'],
        v={'type':'confirmation'})

    if mid == False:
        logger.error('failed to queue email to %s', to)
    else:
        logger.info('queued confirmation email to %s', to)

#-------------------------------------------------------------------------------
def on_delivered():
    '''Mailgun webhook called from view. Has request context'''

    logger.info('confirmation delivered to %s', request.form['recipient'])
