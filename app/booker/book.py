'''app.booker.book'''

import logging
import os
from flask import render_template, request
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse

from .. import etap, utils, gsheets, mailgun
from .. import db
from app.routing.main import order
from app.routing.sheet import append_order
from app.routing.geo import get_gmaps_url

logger = logging.getLogger(__name__)

class EtapError(Exception):
    pass


#-------------------------------------------------------------------------------
def make(agency, data):
    '''Makes the booking in eTapestry by posting to Bravo.
    This function is invoked from the booker client.
    @account: dict with account date. 'date' is dd/mm/yyyy str
    '''

    logger.info('Booking account %s for %s', data['aid'], data['date'])

    response = update_dms(agency, data)

    # is block/date for today and route already built?

    # yyyy-mm-dd format
    event_dt = utils.naive_to_local(
        datetime.combine(
            etap.ddmmyyyy_to_dt(data['date']),
            time(0,0,0))
    )

    route = db.routes.find_one({
        'date': event_dt,
        'block': data['block'],
        'agency': agency}
    )

    if 'ss' in route:
        append_route(agency, route, data)

    if data['send_confirm']:
        send_confirm(agency, data)

    return {
        'status': 'success',
        'description': response
    }

#-------------------------------------------------------------------------------
def update_dms(agency, data):

    conf = db.agencies.find_one({'name':agency})

    try:
        response = etap.call(
          'make_booking',
          conf['etapestry'],
          data={
            'account_num': int(data['aid']),
            'type': 'pickup',
            'udf': {
                'Driver Notes': '***' + data['driver_notes'] + '***',
                'Office Notes': '***RMV ' + data['block'] + ' --' + data['user_fname'] + '***',
                'Block': data['block'],
                'Next Pickup Date': data['date']
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

    return True

#-------------------------------------------------------------------------------
def append_route(agency, route, data):
    '''Block is already routed. Append order to end of Sheet'''

    logger.info('%s already routed for %s. Appending to Sheet.',
                data['block'], data['date'])
    logger.debug('appending to ss_id "%s"', route['ss']['id'])

    conf = db.agencies.find_one({'name':agency})

    acct = etap.call(
        'get_account',
        conf['etapestry'],
        {'account_number': data['aid']}
    )

    service = gsheets.gauth(
        db.agencies.find_one({'name':agency})['google']['oauth']
    )

    _order = order(
        acct,
        [],
        conf['google']['geocode']['api_key'],
        route['driver']['shift_start'],
        '19:00',
        etap.get_udf('Service Time', acct) or 3
    )

    _order['gmaps_url'] = get_gmaps_url(
        _order['location']['name'],
        _order['location']['lat'],
        _order['location']['lng']
    )

    append_order(
        service,
        route['ss']['id'],
        _order
    )

    return True

#-------------------------------------------------------------------------------
def send_confirm(agency, data):
    try:
        body = render_template(
            'email/%s/confirmation.html' % agency,
            http_host = os.environ.get('BRAVO_HTTP_HOST'),
            to = data['email'],
            name = data['name'],
            date_str = etap.ddmmyyyy_to_dt(data['date']).strftime('%B %-d %Y')
        )
    except Exception as e:
        logger.error('Email not sent because render_template error. %s ', str(e))
        pass

    conf = db.agencies.find_one({'name':agency})

    mid = mailgun.send(
        data['email'],
        'Pickup Confirmation',
        body,
        conf['mailgun'],
        v={'type':'confirmation'})

    if mid == False:
        logger.error('failed to queue email to %s', data['email'])
    else:
        logger.info('queued confirmation email to %s', data['email'])

#-------------------------------------------------------------------------------
def on_delivered():
    '''Mailgun webhook called from view. Has request context'''

    logger.info('confirmation delivered to %s', request.form['recipient'])
