'''app.routing.build
Methods can either be called from client user or celery task. Task sets g.group var
'''

import json, requests
from datetime import datetime, time, date
from bson import ObjectId
from dateutil.parser import parse
from flask import g
from app import get_keys
from app.main.etap import call, get_udf, EtapError, get_query
from .main import is_scheduled
from .geo import GeocodeError, geocode, get_gmaps_url
from . import routific, sheet
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def submit_job(route_id):
    '''Submit orders to Routific via asynchronous long-running process endpoint
    API reference: https://docs.routific.com/docs/api-reference
    @date: string format 'Sat Sep 10 2016'
    Returns:
      -String job_id on success
      -False on error'''

    MIN_PER_STOP = 3
    SHIFT_END = '21:00'
    n_skips = 0
    warnings = []
    errors = []
    orders = []
    api_key = get_keys('google')['geocode']['api_key']

    route = g.db.routes.find_one({"_id":ObjectId(route_id)})
    accts = get_query(route['block'], cache=True)

    # Build the orders for Routific
    for acct in accts:
        if is_scheduled(acct, route['date'].date()) == False:
            n_skips += 1
            continue

        try:
            order = create_order(
                acct,
                warnings,
                api_key,
                route['driver']['shift_start'],
                '19:00',
                get_udf('Service Time', acct) or MIN_PER_STOP)
        except EtapError as e:
            errors.append({'acct':acct, 'desc':str(e)})
            continue
        except GeocodeError as e:
            log.exception(e.message, extra={'response':e.message})
            errors.append({'acct':acct, 'desc':str(e)})
            continue
        except requests.RequestException as e:
            errors.append({'acct':acct, 'desc':str(e)})
            continue

        if order == False:
            n_skips += 1
        else:
            orders.append(order)

    office = get_keys('routing')['locations']['office']
    depot = route['depot']

    try:
        office_coords = geocode(office['formatted_address'], api_key)[0]
        depot_coords = geocode(depot['formatted_address'], api_key)[0]
    except GeocodeError as e:
        log.exception('Geocode error', extra={'response':e.response})
        raise

    job_id = routific.submit_vrp_task(
        orders,
        route['driver']['name'],
        office_coords,
        depot_coords,
        route['driver']['shift_start'],
        SHIFT_END,
        get_keys('routing')['routific']['api_key'])

    log.debug('routific job_id=%s', job_id)

    g.db.routes.update_one(
        {'_id': route['_id']},
        {'$set': {
            'job_id': job_id,
            'status': 'processing',
            'block_size': len(accts),
            'orders': len(orders),
            'no_pickups': n_skips,
            'start_address': office['formatted_address'],
            'end_address': depot['formatted_address'],
            'warnings': warnings,
            'errors': errors}})

    if len(errors) > 0:
        log.error('Failed to resolve %s addresses on Route %s',
            len(errors), route['block'], extra={'errors':errors})
    else:
        log.debug('Submitted %s orders to Routific', len(orders),
            extra={'orders':len(orders), 'skips':n_skips, 'warnings':len(warnings)})
    return job_id

#-------------------------------------------------------------------------------
def create_order(acct, warnings, api_key, shift_start, shift_end, stop_time):

    cached = g.db['cachedAccounts'].find_one(
        {'group':g.group, 'account.id':acct['id']})

    if not cached.get('geolocation'):
        cached['geolocation'] = geocode(
            "%s, %s, AB" % (cached['account']['address'],cached['account']['city']),
            get_keys('google')['geocode']['api_key']
        )[0]

    geolocation = cached['geolocation']

    if 'warning' in geolocation:
        warnings.append(geolocation['warning'])

    return routific.order(
        acct,
        "%s, %s, AB" % (acct.get('address'), acct.get('city')),
        geolocation,
        shift_start,
        shift_end,
        stop_time)

#-------------------------------------------------------------------------------
def get_solution(job_id, api_key):
    '''Retrieve async task solution once ready.
    @job_id: routific task_id
    Returns: list of orders from task['output']['solution']['driver'] on
    complete, string on pending status
    Exceptions: requests.RequestException on Routific endpoint error'''

    try:
        task = json.loads(
            requests.get('https://api.routific.com/jobs/'+job_id).text)
    except requests.RequestException as e:
        log.exception('Error retrieving Routific solution')
        raise
    else:
        if task['status'] != 'finished':
            return task['status']
        log.debug('Got solution')

    doc = g.db['routes'].find_one({'job_id':job_id})
    output = task['output']
    orders = task['output']['solution'].get(doc['driver']['name']) or\
        task['output']['solution']['default']
    length = parse(orders[-1]['arrival_time']) - parse(orders[0]['arrival_time'])

    g.db['routes'].update_one({'job_id':job_id},
      {'$set': {
          'status':'finished',
          'orders': task['visits'],
          'total_travel_time': output['total_travel_time'],
          'num_unserved': output['num_unserved'],
          'routific': {
              'input': task['input']['visits'],
              'solution': task['output']['solution']},
          'duration': length.seconds/60}})

    if not doc:
        log.error("No mongo record for job_id '%s'", job_id)
        return False

    # Add custom fields in solution obj
    for order in orders:
        if order['location_id'] == 'office':
            continue
        elif order['location_id'] == 'depot':
            location = geocode(doc['end_address'],api_key)[0]['geometry']['location']
            order['customNotes'] = {'id':'depot', 'name':'Depot'}
            order['gmaps_url'] = get_gmaps_url(
                order['location_name'], location['lat'], location['lng'])
        else:
            input_ = task['input']['visits'][order['location_id']]
            order['customNotes'] = input_['customNotes']
            order['gmaps_url'] = get_gmaps_url(
                input_['location']['name'], input_['location']['lat'], input_['location']['lng'])

    office = get_keys('routing')['locations']['office']

    orders.append({
        "location_id":"office",
        "location_name": office['formatted_address'],
        "arrival_time":"",
        "finish_time":"",
        "gmaps_url": office['url'],
        "customNotes": {
            "id": "office",
            "name": office['name']}})
    return orders
