'''app.booker.book'''
import os
from flask import g, render_template, request
from datetime import datetime, time
from .. import get_keys
from app.lib import gsheets, mailgun
from app.lib.dt import to_local, to_utc, ddmmyyyy_to_dt
from app.lib.loggy import Loggy
from app.main.etap import EtapError, call, get_udf
from app.routing.build import create_order
from app.routing.sheet import append_order
from app.routing.geo import get_gmaps_url
log = Loggy('book')

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
        log.error('failed to book: %s', str(e))
        pass

    # is block/date for today and route already built?

    event_dt = to_utc(
        d=ddmmyyyy_to_dt(request.form['date']).date(),
        t=time(8,0))

    route = g.db.routes.find_one({
        'date': event_dt,
        'block': request.form['block'],
        'agency': g.user.agency})

    append = True if route and route.get('ss') else False

    if append:
        append_to(route)

    email_conf = request.form.get('confirmation')

    if email_conf == 'true':
        send_confirm()

    log.info('booked acct %s for %s. email conf=%s, append order=%s',
        request.form['aid'], request.form['date'], email_conf, append)

    return "Booked successfully"

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
                    (request.form['block'], g.user.name),
                'Block': request.form['block'],
                'Next Pickup Date': request.form['date']}})
    except EtapError as e:
        pass
    except Exception as e:
        pass

    return True

#-------------------------------------------------------------------------------
def append_to(route):
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

    wks = get_keys('routing',agcy=route['agency'])['gdrive']['template_orders_wks_name']

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
        log.debug('queued confirmation email to %s', request.form['email'])

#-------------------------------------------------------------------------------
def on_delivered(agcy=None):
    '''Mailgun webhook called from view. Has request context'''

    log.debug('confirmation delivered to %s', request.form['recipient'])
