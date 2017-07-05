'''app.booker.book'''
import os
from flask import g, render_template, request
from datetime import datetime, time
from .. import get_keys
from app.lib import gsheets, mailgun
from app.lib.dt import to_local, to_utc, ddmmyyyy_to_dt
from app.main.etap import EtapError, call, get_udf
from app.routing.build import create_order
from app.routing.sheet import append_order
from app.routing.geo import get_gmaps_url
from logging import getLogger
log = getLogger(__name__)

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

    try:
        response = update_dms()
    except Exception as e:
        log.exception('Error updating account with Booking request')
        raise

    # is block/date for today and route already built?

    event_dt = to_utc(
        d=ddmmyyyy_to_dt(request.form['date']).date(),
        t=time(8,0))

    route = g.db.routes.find_one({
        'date': event_dt,
        'block': request.form['block'],
        'group': g.group})

    append = True if route and route.get('ss') else False

    if append:
        append_to(route)

    email_conf = request.form.get('confirmation')

    if email_conf == 'true':
        send_confirm()

    log.info('Booked account ID %s on %s for %s',
        request.form['aid'], request.form['block'],
        ddmmyyyy_to_dt(request.form['date']).strftime('%b %d'),
        extra={'email_confirmation':email_conf, 'append_to_route': append})

    return "Booked successfully"

#-------------------------------------------------------------------------------
def update_dms():

    try:
        response = call('make_booking',
          data= {
            'acct_id': int(request.form['aid']),
            'type': 'pickup',
            'udf': {
                'Driver Notes': '***%s***' % request.form['driver_notes'],
                'Office Notes': '***RMV %s --%s***' %
                    (request.form['block'], g.user.name),
                'Block': request.form['block'],
                'Next Pickup Date': request.form['date']}})
    except EtapError as e:
        raise
    except Exception as e:
        raise

    return True

#-------------------------------------------------------------------------------
def append_to(route):
    '''Block is already routed. Append order to end of Sheet'''

    log.info('%s already routed for %s. Appending to Sheet.',
        request.form['block'], request.form['date'])
    log.debug('appending to ss_id "%s"', route['ss']['id'])

    acct = call('get_acct', data={'acct_id': request.form['aid']})

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

    wks = get_keys('routing',group=route['agency'])['gdrive']['template_orders_wks_name']

    append_order(
        service,
        route['ss']['id'],
        wks,
        order)

    return True

#-------------------------------------------------------------------------------
def send_confirm():
    try:
        body = render_template(
            'email/%s/confirmation.html' % g.group,
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
        v={'group':g.group, 'type':'booking'})

    if mid == False:
        log.error('failed to queue email to %s', request.form['email'])
    else:
        log.debug('queued confirmation email to %s', request.form['email'])

#-------------------------------------------------------------------------------
def on_delivered(group=None):
    '''Mailgun webhook called from view. Has request context'''

    log.debug('confirmation delivered to %s', request.form['recipient'])
