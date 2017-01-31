'''app.booker.book'''
import logging, os
from flask import g, render_template, request
from datetime import datetime, time
from .. import gsheets, mailgun
from app.etap import EtapError, call, get_udf
from app.dt import to_local, ddmmyyyy_to_dt
from app.routing.build import create_order
from app.routing.sheet import append_order
from app.routing.geo import get_gmaps_url
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def make(data):
    '''Makes the booking in eTapestry by posting to Bravo.
    This function is invoked from the booker client.
    @account: dict with account date. 'date' is dd/mm/yyyy str
    '''

    log.info('Booking account %s for %s', data['aid'], data['date'])

    response = update_dms(data)

    # is block/date for today and route already built?

    # yyyy-mm-dd format
    event_dt = to_local(ddmmyyyy_to_dt(data['date']))

    route = g.db.routes.find_one({
        'date': event_dt,
        'block': data['block'],
        'agency': g.user.agency})

    if route and route.get('ss'):
        append_route(g.user.agency, route, data)

    if data['send_confirm']:
        send_confirm(data)

    return {
        'status': 'success',
        'description': response}

#-------------------------------------------------------------------------------
def update_dms(data):

    try:
        response = etap.call(
          'make_booking',
          get_keys('etapestry'),
          data={
            'account_num': int(data['aid']),
            'type': 'pickup',
            'udf': {
                'Driver Notes': '***' + data['driver_notes'] + '***',
                'Office Notes': '***RMV ' + data['block'] + ' --' + data['user_fname'] + '***',
                'Block': data['block'],
                'Next Pickup Date': data['date']}})
    except EtapError as e:
        return {
            'status': 'failed',
            'description': 'etapestry error: %s' % str(e)}
    except Exception as e:
        log.error('failed to book: %s', str(e))
        return {
            'status': 'failed',
            'description': str(e)}

    return True

#-------------------------------------------------------------------------------
def append_route(route, data):
    '''Block is already routed. Append order to end of Sheet'''

    log.info('%s already routed for %s. Appending to Sheet.',
                data['block'], data['date'])
    log.debug('appending to ss_id "%s"', route['ss']['id'])

    acct = etap.call(
        'get_account',
        get_keys('etapestry'),
        {'account_number': data['aid']})

    service = gsheets.gauth(get_keys('google')['oauth'])

    order = create_order(
        acct,
        [],
        get_keys('google')['geocode']['api_key'],
        route['driver']['shift_start'],
        '19:00',
        etap.get_udf('Service Time', acct) or 3)

    order['gmaps_url'] = get_gmaps_url(
        order['location']['name'],
        order['location']['lat'],
        order['location']['lng'])

    append_order(
        service,
        route['ss']['id'],
        order)

    return True

#-------------------------------------------------------------------------------
def send_confirm(data):
    try:
        body = render_template(
            'email/%s/confirmation.html' % g.user.agency,
            to = data['email'],
            name = data['name'],
            date_str = ddmmyyyy_to_dt(data['date']).strftime('%B %-d %Y'))
    except Exception as e:
        log.error('Email not sent because render_template error. %s ', str(e))
        pass

    mid = mailgun.send(
        data['email'],
        'Pickup Confirmation',
        body,
        get_keys('mailgun'),
        v={'agcy':g.user.agency, 'type':'confirmation'})

    if mid == False:
        log.error('failed to queue email to %s', data['email'])
    else:
        log.info('queued confirmation email to %s', data['email'])

#-------------------------------------------------------------------------------
def on_delivered():
    '''Mailgun webhook called from view. Has request context'''

    log.info('confirmation delivered to %s', request.form['recipient'])
