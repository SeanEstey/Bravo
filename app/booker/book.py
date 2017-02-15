'''app.booker.book'''
import logging, os
from flask import g, render_template, request
from datetime import datetime, time
from .. import get_keys, gsheets, mailgun
from app.etap import EtapError, call, get_udf
from app.dt import to_local, ddmmyyyy_to_dt
from app.routing.build import create_order
from app.routing.sheet import append_order
from app.routing.geo import get_gmaps_url
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def make():
    '''Makes the booking in eTapestry by posting to Bravo.
    This function is invoked from the booker client.
    @account: dict with account date. 'date' is dd/mm/yyyy str
    @request.form: {
        'block': block,
        'date': date,
        'aid': aid,
        'driver_notes': notes,
        'first_name': name,
        'email': email,
        'confirmation': confirmation}
    '''

    log.info('Booking account %s for %s', request.form['aid'], request.form['date'])

    response = update_dms()

    # is block/date for today and route already built?

    # yyyy-mm-dd format
    event_dt = to_local(ddmmyyyy_to_dt(request.form['date']))

    route = g.db.routes.find_one({
        'date': event_dt,
        'block': request.form['block'],
        'agency': g.user.agency})

    if route and route.get('ss'):
        append_route(route)

    if request.form.get('confirmation') == 'true':
        send_confirm()

    return {
        'status': 'success',
        'description': response}

#-------------------------------------------------------------------------------
def update_dms():

    try:
        response = call(
          'make_booking',
          get_keys('etapestry'),
          data={
            'acct_id': int(request.form['aid']),
            'type': 'pickup',
            'udf': {
                'Driver Notes': '***%s***' % request.form['driver_notes'],
                'Office Notes': '***RMV %s --%s***' %
                    (request.form['block'], request.form['first_name']),
                'Block': request.form['block'],
                'Next Pickup Date': request.form['date']}})
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
def append_route(route):
    '''Block is already routed. Append order to end of Sheet'''

    log.info('%s already routed for %s. Appending to Sheet.',
                request.form['block'], request.form['date'])
    log.debug('appending to ss_id "%s"', route['ss']['id'])

    acct = call(
        'get_acct',
        get_keys('etapestry'),
        {'acct_id': request.form['aid']})

    service = gsheets.gauth(get_keys('google')['oauth'])

    order = create_order(
        acct,
        [],
        get_keys('google')['geocode']['api_key'],
        route['driver']['shift_start'],
        '19:00',
        get_udf('Service Time', acct) or 3)

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
def send_confirm():
    try:
        body = render_template(
            'email/%s/confirmation.html' % g.user.agency,
            to = request.form['email'],
            name = request.form['first_name'],
            date_str = ddmmyyyy_to_dt(request.form['date']).strftime('%B %-d %Y'))
    except Exception as e:
        log.error('template error. desc=%s', str(e))
        log.debug('', exc_info=True)
        pass

    mid = mailgun.send(
        request.form['email'],
        'Pickup Confirmation',
        body,
        get_keys('mailgun'),
        v={'agcy':g.user.agency, 'type':'booking'})

    if mid == False:
        log.error('failed to queue email to %s', request.form['email'])
    else:
        log.info('queued confirmation email to %s', request.form['email'])

#-------------------------------------------------------------------------------
def on_delivered():
    '''Mailgun webhook called from view. Has request context'''

    log.info('confirmation delivered to %s', request.form['recipient'])
