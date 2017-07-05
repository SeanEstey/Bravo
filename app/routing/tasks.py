# app.routing.tasks

import logging, json, re, pytz
from time import sleep
from bson import ObjectId as oid
from flask import g
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
from app import celery, get_keys, get_group
from app.lib import gcal, gdrive, gsheets, timer
from app.lib.utils import format_bson
from app.lib.dt import to_local, ddmmyyyy_to_date
from app.lib.timer import Timer
from app.main import parser
from app.main.etapestry import EtapError, get_udf
from .main import add_metadata
from .build import submit_job, get_solution
from . import depots, sheet, routific

log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def discover_routes(self, group, within_days=5, **rest):
    '''Scans schedule for blocks, adds metadata to db'''

    g.group = group

    from app.main.socketio import smart_emit

    sleep(3)

    smart_emit('discover_routes', {'status':'in-progress'})
    log.debug('Discovering routes...')
    n_found = 0
    events = []
    service = gcal.gauth(get_keys('google')['oauth'])
    cal_ids = get_keys('cal_ids')

    for _id in cal_ids:
        start = to_local(d=date.today())

        events += gcal.get_events(
            service,
            cal_ids[_id],
            start,
            start + timedelta(days=within_days))

    events = sorted(events, key=lambda k: k['start'].get('date'))

    for event in events:
        block = parser.get_block(event['summary'])
        event_dt = to_local(d=parse(event['start']['date']), t=time(8,0))

        if not block:
            continue
        if not g.db.routes.find_one(
            {'date':event_dt.astimezone(pytz.utc), 'block': block, 'agency':g.group}
        ):
            try:
                meta = add_metadata(block, event_dt, event)
            except Exception as e:
                log.exception('Error writing route %s metadata', block)
                continue

            log.debug('discovered %s on %s', block, event_dt.strftime('%b %-d'))
            smart_emit('discover_routes', {
                'status': 'discovered', 'route': format_bson(meta)},
                room=g.group)

            n_found +=1

    smart_emit('discover_routes', {'status':'completed'}, room=g.group)
    return 'discovered %s routes' % n_found

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def build_scheduled_routes(self, group=None, **rest):
    '''Route orders for today's Blocks and build Sheets
    '''

    groups = [get_keys(group=group)] if group else g.db['groups'].find()

    for group_ in groups:
        g.group = group_['name']
        n_fails = n_success = 0

        log.info("Task: Building scheduled routes...")

        routes = g.db.routes.find(
            {'agency':g.group, 'date':to_local(d=date.today(),t=time(8,0))})

        discover_routes(g.group)

        for route in routes:
            try:
                build_route(str(route['_id']))
            except Exception as e:
                log.exception('Error building route %s', route['block'],
                    extra={'route_id':str(route['_id'])})
                n_fails+=1
                continue

            n_success += 1
            sleep(2)

        if n_fails == 0:
            log.info('Task completed. Built %s/%s scheduled routes',
                n_success, n_success + n_fails)
        else:
            log.error('Built %s/%s scheduled routes. Click for error details.',
                n_success, n_success + n_fails)
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

    from app.routing.geo import GeocodeError

    timer = Timer()
    orders = "processing"
    route = g.db.routes.find_one({"_id":oid(route_id)})
    g.group = route['agency']
    oauth = get_keys('google')['oauth']
    api_key = get_keys('google')['geocode']['api_key']

    log.debug('Building route %s...', route['block'],
        extra={'route_id':route_id, 'job_id':job_id or None})

    if job_id is None:
        try:
            job_id = submit_job(oid(route_id))
        except GeocodeError as e:
            log.exception('Geocoding error.', extra={'response':e.response})
            raise

    while orders == "processing":
        log.debug('No solution yet...')
        sleep(5)
        orders = get_solution(job_id, api_key)

    title = '%s: %s (%s)' %(route['date'].strftime('%b %-d'), route['block'], route['driver']['name'])
    ss = sheet.build(gdrive.gauth(oauth), title)
    route = g.db['routes'].find_one_and_update({'_id':oid(route_id)}, {'$set':{'ss':ss}})
    wks_name = get_keys('routing')['gdrive']['template_orders_wks_name']

    try:
        service = gsheets.gauth(oauth)
        sheet.write_orders(service, ss['id'], wks_name, orders)
        sheet.write_prop(service, ss['id'], route)

        for e in route['errors']:
            # Append any non-geocodable orders
            order = routific.order(e['acct'], e['acct']['address'], {}, '', '',0)
            sheet.append_order(service, ss['id'], wks_name, order)
    except Exception as e:
        log.exception('Error writing to Sheets')
        raise

    #smart_emit('route_status',{
    #    'status':'completed', 'ss_id':ss['id'], 'warnings':route['warnings']})

    log.info('Built route %s [%s]', route['block'], timer.clock(),
        extra={'n_orders':len(orders), 'n_unserved': route['num_unserved'],
               'n_warnings': len(route['warnings']), 'n`_errors': len(route['errors'])})

    return json.dumps({'status':'success', 'route_id':str(route['_id'])})
