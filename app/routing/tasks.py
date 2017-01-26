'''app.routing.tasks'''
import logging, re
from time import sleep
from bson import ObjectId
import bson.json_util
from flask import g
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
from .. import smart_emit, celery, get_keys, gcal, gdrive, gsheets, etap, parser
from ..utils import local_today_dt, d_to_local_dt, formatter
from ..etap import EtapError, get_query, get_udf
from . import depots, sheet
from .main import submit_job, get_solution_orders
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def discover_routes(self, agcy=None, within_days=5, **rest):
    '''Celery task
    Scans schedule for blocks, adds metadata to db, sends socketio signal
    to client
    '''

    #sleep(3)
    log.debug('discover_routes, days=%s, g.user=%s', within_days, g.user)
    smart_emit('discover_routes', {'status':'in-progress'})

    n_found = 0
    events = []
    service = gcal.gauth(get_keys('google')['oauth'])
    cal_ids = get_keys('cal_ids')

    for _id in cal_ids:
        events += gcal.get_events(
            service,
            cal_ids[_id],
            local_today_dt(),
            local_today_dt() + timedelta(days=within_days))

    events = sorted(events, key=lambda k: k['start'].get('date'))

    for event in events:
        block = parser.get_block(event['summary'])
        event_d = parse(event['start']['date']) # yyyy-mm-dd
        event_dt = d_to_local_dt(event_d)

        if not block:
            continue

        if g.db.routes.find_one({
            'date':event_dt,
            'block': block,
            'agency':g.user.agency}
        ):
            continue

        # Build route metadata

        try:
            accts = etap.get_query(block, get_keys('etapestry'))
        except EtapError as e:
            log.error('Error retrieving query=%s', block)
            continue

        n_drops = n_booked = 0

        for acct in accts:
            npu = get_udf('Next Pickup Date', acct)

            if npu == '':
                continue

            npu_d = etap.ddmmyyyy_to_date(npu)

            if npu_d == event_d:
                n_booked += 1

            if get_udf('Status', acct) == 'Dropoff':
                n_drops += 1

        postal = re.sub(r'\s', '', event['location']).split(',')

        if len(get_keys('routing')['locations']['depots']) > 1:
            depot = depots.resolve(block, postal)
        else:
            depot = get_keys('routing')['locations']['depots'][0]

        meta = {
          'block': block,
          'date': event_dt,
          'agency': g.user.agency,
          'status': 'pending',
          'postal': re.sub(r'\s', '', event['location']).split(','),
          'depot': depot,
          'driver': get_keys('routing')['drivers'][0], # default driver
          'orders': n_booked,
          'block_size': len(accts),
          'dropoffs': n_drops
        }

        g.db.routes.insert_one(meta)

        log.debug('discovered %s on %s', block, event_dt.strftime('%b %-d'))

        smart_emit('add_route_metadata', {
            'data': formatter(meta, to_strftime=True, bson_to_json=True)},
            room=g.user.agency)

        n_found +=1

    smart_emit('discover_routes', {'status':'completed'}, room=g.user.agency)

    log.debug('discovered %s routes', n_found)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def build_scheduled_routes(self, agcy=None, **rest):
    '''Route orders for today's Blocks and build Sheets
    '''

    if agcy:
        agencies = [g.db.agencies.find_one({'name':agcy})]
    else:
        agencies = g.db.agencies.find({})

    for agency in agencies:
        agcy = agency['name']
        n_success = n_fails = 0
        routes = g.db.routes.find({'agency':agcy, 'date':local_today_dt()})

        discover_routes()

        log.info('%s: Building %s routes for %s',
            agcy, routes.count(), date.today().strftime("%A %b %d"))

        n_fails = n_success = 0

        for route in routes:
            try:
                build_route(str(route['_id']))
            except Exception as e:
                log.error('Error building %s, msg=%s', route['block'], str(e))
                n_fails+=1
                continue

            n_success += 1
            sleep(2)

        log.info('%s: %s Routes built. %s failures.', agcy, n_success, n_fails)

    return 'success'

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def build_route(self, route_id, job_id=None, **rest):
    '''Celery task that routes a Block via Routific and writes orders to a Sheet
    Can take up to a few min to run depending on size of route, speed of
    dependent API services (geocoder, sheets/drive api)
    @route_id: '_id' of record in 'routes' db collection (str)
    @job_id: routific job string. If passed, creates Sheet without re-routing
    Returns: db.routes dict on success, False on error
    '''

    log.debug('route_id=%s, job_id=%s, rest=%s', route_id, job_id, rest)

    route = g.db.routes.find_one({"_id":ObjectId(route_id)})
    agcy = route['agency']

    log.info('%s: Building %s...', agcy, route['block'])

    if job_id is None:
        job_id = submit_job(ObjectId(route_id))

    # Keep looping and sleeping until receive solution or hit task_time_limit
    orders = get_solution_orders(
        job_id,
        get_keys('google',agcy=agcy)['geocode']['api_key'])

    if orders == False:
        log.error('Error retrieving routific solution')
        return 'failed'

    while orders == "processing":
        log.debug('No solution yet. Sleeping 5s...')
        sleep(5)
        orders = get_solution_orders(
            job_id,
            get_keys('google',agcy=agcy)['geocode']['api_key'])

    title = '%s: %s (%s)' %(
        route['date'].strftime('%b %-d'), route['block'], route['driver']['name'])

    ss = sheet.build(
        agcy,
        gdrive.gauth(get_keys('google',agcy=agcy)['oauth']),
        title)

    route = g.db.routes.find_one_and_update(
        {'_id':ObjectId(route_id)},
        {'$set':{ 'ss': ss}}
    )

    sheet.write_orders(
        gsheets.gauth(get_keys('google',agcy=agcy)['oauth']),
        ss['id'],
        orders)

    smart_emit('route_status',{
        'status':'completed', 'ss_id':ss['id'], 'warnings':route['warnings']})

    log.info(
        '%s Sheet created. Orders written.', route['block'])

    return 'success'
