'''app.routing.build'''
import json, requests
from datetime import datetime, time, date
from bson import ObjectId
from dateutil.parser import parse
from flask import g
from app import get_keys
from app.main.etap import call, get_udf, EtapError
from .main import is_scheduled
from .geo import geocode, get_gmaps_url
from . import routific, sheet
from logging import getLogger
log = getLogger(__name__)

class GeocodeError(Exception):
    pass

'''Methods can either be called from client user or celery task. Task
sets g.group var'''

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
    num_skips = 0
    warnings = []
    errors = []
    orders = []

    route = g.db.routes.find_one({"_id":ObjectId(route_id)})
    etap_keys = get_keys('etapestry')
    accts = call('get_query', get_keys('etapestry'), {
        "query":route['block'],
        "category":etap_keys['query_category']}
    )['data']

    # Build the orders for Routific
    for acct in accts:
        if is_scheduled(acct, route['date'].date()) == False:
            num_skips += 1
            continue

        try:
            order = create_order(
                acct,
                warnings,
                get_keys('google')['geocode']['api_key'],
                route['driver']['shift_start'],
                '19:00',
                get_udf('Service Time', acct) or MIN_PER_STOP)
        except EtapError as e:
            errors.append(str(e))
            continue
        except GeocodeError as e:
            log.error('GeocodeError exception')
            errors.append(str(e))
            continue
        except requests.RequestException as e:
            errors.append(str(e))
            continue

        if order == False:
            num_skips += 1
        else:
            orders.append(order)

    log.debug('orders=%s, skips=%s, geo_warnings=%s, geo_errors=%s',
        len(orders), num_skips, len(warnings), len(errors))

    office = get_keys('routing')['locations']['office']
    office_coords = geocode(
        office['formatted_address'],
        get_keys('google')['geocode']['api_key'])[0]
    depot = route['depot']
    depot_coords = geocode(
        depot['formatted_address'],
        get_keys('google')['geocode']['api_key'])[0]

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
            'no_pickups': num_skips,
            'start_address': office['formatted_address'],
            'end_address': depot['formatted_address'],
            'warnings': warnings,
            'errors': errors}})

    return job_id

#-------------------------------------------------------------------------------
def create_order(acct, warnings, api_key, shift_start, shift_end, min_per_stop):
    '''Returns:
      -Dict order on success
    Exceptions:
      -requests.RequestException on geocode service error
      -EtapError on missing or invalid account data
      -GeocodeError on unable to resolve address'''

    if not acct.get('address') or not acct.get('city'):
        msg = \
          "Routing error: account <strong>%s</strong> missing address/city." % acct['id']

        log.error(msg)
        raise EtapError(msg)
    else:
        formatted_address = acct['address'] + ', ' + acct['city'] + ', AB'

    try:
        geo_result = geocode(
            formatted_address,
            api_key,
            postal=acct['postalCode'])
    except requests.RequestException as e:
        log.error(str(e))
        raise

    if len(geo_result) == 0:
        msg = \
            "Unable to resolve address <strong>%s, %s</strong>." %(
            acct['address'],acct['city'])

        log.error(msg)
        raise GeocodeError(msg)

    geo_result = geo_result[0]

    if 'warning' in geo_result:
        warnings.append(geo_result['warning'])

    return routific.order(
        acct,
        formatted_address,
        geo_result,
        shift_start,
        shift_end,
        min_per_stop)

#-------------------------------------------------------------------------------
def get_solution_orders(job_id, api_key):
    '''Check Routific for status of asynchronous long-running task
    Job statuses: ['pending', 'processing', 'finished']
    Solution statuses: ['success', ??]
    @job_id: routific id (str)
    @api_key: google geocode api key
    Returns:
      -List of orders from task['output']['solution']['driver'] on
      task['status'] == 'finished'
      -String task['status'] on incomplete
    Exceptions:
      -Raises requests.RequestException on Routific endpoint error'''

    try:
        r = requests.get('https://api.routific.com/jobs/' + job_id)
    except requests.RequestException as e:
        log.error('Error calling api.routific.com/jobs: %s', str(e))
        raise

    task = json.loads(r.text)

    if task['status'] != 'finished':
        return task['status']

    route_info = g.db.routes.find_one({'job_id':job_id})

    output = task['output']
    orders = task['output']['solution'].get(route_info['driver']['name']) or\
        task['output']['solution']['default']

    log.debug('retrieved solution. route_length=%smin', output['total_travel_time'])

    route_length = parse(orders[-1]['arrival_time']) - parse(orders[0]['arrival_time'])

    g.db.routes.update_one({'job_id':job_id},
      {'$set': {
          'status':'finished',
          'orders': task['visits'],
          'total_travel_time': output['total_travel_time'],
          'num_unserved': output['num_unserved'],
          'routific': {
              'input': task['input']['visits'],
              'solution': task['output']['solution']},
          'duration': route_length.seconds/60}})

    if not route_info:
        log.error("No mongo record for job_id '%s'", job_id)
        return False

    # Routific doesn't include custom fields in the solution object.
    # Copy them over manually.
    # Also create Google Maps url

    for order in orders:
        if order['location_id'] == 'office':
            continue
        elif order['location_id'] == 'depot':
            # TODO: Add proper depot name, phone number, hours, and unload duration

            location = geocode(
                route_info['end_address'], api_key
            )[0]['geometry']['location']

            order['customNotes'] = {
                'id': 'depot',
                'name': 'Depot'}
            order['gmaps_url'] = get_gmaps_url(
                order['location_name'],
                location['lat'],
                location['lng'])
        # Regular order
        else:
            input_ = task['input']['visits'][order['location_id']]
            order['customNotes'] = input_['customNotes']

            order['gmaps_url'] = get_gmaps_url(
                input_['location']['name'],
                input_['location']['lat'],
                input_['location']['lng'])

    office = get_keys('routing')['locations']['office']

    # Add office stop
    # TODO: Add travel time from depot to office
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
