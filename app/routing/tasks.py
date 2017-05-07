'''app.routing.tasks'''
import json, re, pytz
from time import sleep
from bson import ObjectId
from flask import g
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
from app import smart_emit, celery, get_keys, get_group
from app.lib import gcal, gdrive, gsheets
from app.lib.utils import formatter
from app.lib.dt import to_local, ddmmyyyy_to_date
from app.main import parser
from app.main.etap import EtapError, get_udf
from .main import add_metadata
from .build import submit_job, get_solution_orders
from . import depots, sheet
from logging import getLogger
log = getLogger('worker.%s'%__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def discover_routes(self, agcy, within_days=5, **rest):
    '''Celery task
    Scans schedule for blocks, adds metadata to db, sends socketio signal
    to client
    '''

    sleep(3)
    g.group = agcy
    smart_emit('discover_routes', {'status':'in-progress'})
    log.debug('discovering routes...')
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

        if not g.db.routes.find_one({
            'date':event_dt.astimezone(pytz.utc),
            'block': block,
            'agency':g.group}):

            try:
                meta = add_metadata(block, event_dt, event)
            except Exception as e:
                log.debug('block %s raised exc. continuing...', block)
                continue

            log.debug('discovered %s on %s',
                block, event_dt.strftime('%b %-d'))

            smart_emit('discover_routes', {
                'status': 'discovered', 'route': formatter(meta, to_strftime=True, bson_to_json=True)},
                room=g.group)

            n_found +=1

    smart_emit('discover_routes', {'status':'completed'}, room=g.group)

    return 'discovered %s routes' % n_found

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def build_scheduled_routes(self, agcy=None, **rest):
    '''Route orders for today's Blocks and build Sheets
    '''

    g.group = agcy
    log.warning('task: building scheduled routes...')

    agcy_list = [get_keys()] if agcy else g.db.agencies.find()
    n_fails = n_success = 0

    for agency in agcy_list:
        g.group = agency['name']
        routes = g.db.routes.find({
            'agency':g.group,
            'date':to_local(d=date.today(),t=time(8,0))})

        discover_routes(g.group)

        log.info('building %s routes', routes.count())

        for route in routes:
            try:
                build_route(str(route['_id']))
            except Exception as e:
                log.error('error building %s, msg=%s', route['block'], str(e))
                n_fails+=1
                continue

            n_success += 1
            sleep(2)

    log.warning('task: completed. %s routes built, %s failures.', n_success, n_fails)
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

    route = g.db.routes.find_one({"_id":ObjectId(route_id)})
    g.group = route['agency']

    log.debug('route_id="%s", job_id="%s"', route_id, job_id)
    log.info('building %s...', route['block'])

    if job_id is None:
        job_id = submit_job(ObjectId(route_id))

    # Keep looping and sleeping until receive solution or hit task_time_limit
    orders = get_solution_orders(
        job_id,
        get_keys('google')['geocode']['api_key'])

    if orders == False:
        log.error('error retrieving routific solution')
        log.debug(str(e))
        return 'failed'

    while orders == "processing":
        log.debug('no solution yet, sleeping (5s)...')
        sleep(5)
        orders = get_solution_orders(
            job_id,
            get_keys('google')['geocode']['api_key'])

    title = '%s: %s (%s)' %(
        route['date'].strftime('%b %-d'), route['block'], route['driver']['name'])

    ss = sheet.build(
        gdrive.gauth(get_keys('google')['oauth']),
        title)

    route = g.db.routes.find_one_and_update(
        {'_id':ObjectId(route_id)},
        {'$set':{ 'ss': ss}})

    try:
        service = gsheets.gauth(get_keys('google')['oauth'])
        sheet.write_orders(
            service,
            ss['id'],
            get_keys('routing')['gdrive']['template_orders_wks_name'],
            orders)
        sheet.write_prop(
            g.group,
            service,
            ss['id'],
            route)
    except Exception as e:
        log.error('error writing orders. desc=%s', str(e))
        log.debug(str(e))
        raise

    smart_emit('route_status',{
        'status':'completed', 'ss_id':ss['id'], 'warnings':route['warnings']})

    log.info('%s built. orders=%s, unserved=%s, warnings=%s, errors=%s',
        route['block'], len(orders), route['num_unserved'],
        len(route['warnings']), len(route['errors']))

    return json.dumps({'status':'success', 'route_id':str(route['_id'])})
