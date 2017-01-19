'''app.routing.routes'''

import json
import logging
from dateutil.parser import parse
from datetime import datetime, time, date
from time import sleep
import requests
from flask_login import current_user
from bson import ObjectId
from .. import celery_sio, get_db, gdrive, gsheets, etap, cal, utils
from . import geo, routific, sheet
logger = logging.getLogger(__name__)

class GeocodeError(Exception):
    pass
class EtapBadDataError(Exception):
    pass

#-------------------------------------------------------------------------------
def build(route_id, job_id=None):
    '''Celery task that routes a Block via Routific and writes orders to a Sheet
    Can take up to a few min to run depending on size of route, speed of
    dependent API services (geocoder, sheets/drive api)
    @route_id: '_id' of record in 'routes' db collection (str)
    @job_id: routific job string. If passed, creates Sheet without re-routing
    Returns: db.routes dict on success, False on error
    '''

    db = get_db()
    route = db.routes.find_one({"_id":ObjectId(route_id)})
    conf = db['agencies'].find_one({'name':route['agency']})

    logger.info('%s: Building %s...', route['agency'], route['block'])

    if job_id is None:
        job_id = submit_job(ObjectId(route_id))

    # Keep looping and sleeping until receive solution or hit
    # CELERYD_TASK_TIME_LIMIT (3000 s)
    orders = get_solution_orders(job_id, conf['google']['geocode']['api_key'])

    if orders == False:
        logger.error('Error retrieving routific solution')
        return False

    while orders == "processing":
        logger.debug('No solution yet. Sleeping 5s...')
        sleep(5)
        orders = get_solution_orders(job_id, conf['google']['geocode']['api_key'])

    title = '%s: %s (%s)' %(
        route['date'].strftime('%b %-d'), route['block'], route['driver']['name'])

    ss = sheet.build(
        conf['name'],
        gdrive.gauth(conf['google']['oauth']),
        title)

    route = db.routes.find_one_and_update(
        {'_id':ObjectId(route_id)},
        {'$set':{ 'ss': ss}}
    )

    sheet.write_orders(
        gsheets.gauth(conf['google']['oauth']),
        ss['id'],
        orders)

    celery_sio.emit('route_status', {
        'agency': conf['name'],
        'status':'completed',
        'ss_id': ss['id'],
        'warnings': route['warnings']})

    logger.info(
        '%s Sheet created. Orders written.', route['block'])

    return route

#-------------------------------------------------------------------------------
def submit_job(route_id):
    '''Submit orders to Routific via asynchronous long-running process endpoint
    API reference: https://docs.routific.com/docs/api-reference
    @date: string format 'Sat Sep 10 2016'
    Returns:
      -String job_id on success
      -False on error'''

    MIN_PER_STOP = 3
    SHIFT_END = '19:00'

    db = get_db()
    route = db.routes.find_one({"_id":ObjectId(route_id)})
    conf = db.agencies.find_one({'name':route['agency']})

    accounts = etap.call(
        'get_query_accounts',
        conf['etapestry'], {
            "query": route['block'],
            "query_category": conf['etapestry']['query_category']
        }
    )['data']

    num_skips = 0
    warnings = []
    errors = []
    orders = []

    # Build the orders for Routific
    for account in accounts:
        if is_scheduled(account, route['date'].date()) == False:
            num_skips += 1
            continue

        try:
            _order = order(
                account,
                warnings,
                conf['google']['geocode']['api_key'],
                route['driver']['shift_start'],
                '19:00',
                etap.get_udf('Service Time', account) or MIN_PER_STOP
            )
        except EtapBadDataError as e:
            errors.append(str(e))
            continue
        except GeocodeError as e:
            logger.error('GeocodeError exception')
            errors.append(str(e))
            continue
        except requests.RequestException as e:
            errors.append(str(e))
            continue

        if order == False:
            num_skips += 1
        else:
            orders.append(_order)

    logger.debug('Omitting %s no pickups', str(num_skips))

    start_address = conf['routing']['locations']['office']['formatted_address']
    end_address = route['depot']['formatted_address']

    job_id = routific.submit_vrp_task(
        orders,
        route['driver']['name'],
        geo.geocode(
            start_address,
            conf['google']['geocode']['api_key'])[0],
        geo.geocode(
            end_address,
            conf['google']['geocode']['api_key'])[0],
        route['driver']['shift_start'],
        SHIFT_END,
        conf['routing']['routific']['api_key']
    )

    logger.info(
        '\nSubmitted routific task\n'\
        'Job_id: %s\nOrders: %s\n'\
        'Min/stop: %s',
        job_id, len(orders), MIN_PER_STOP)

    db.routes.update_one(
        {'agency': conf['name'],
         'block': route['block'],
         'date': utils.naive_to_local(datetime.combine(route['date'].date(), time(0,0,0)))},
        {'$set': {
            'job_id': job_id,
            'status': 'processing',
            'block_size': len(accounts),
            'orders': len(orders),
            'no_pickups': num_skips,
            'start_address': start_address,
            'end_address': end_address,
            'warnings': warnings,
            'errors': errors
        }})

    return job_id

#-------------------------------------------------------------------------------
def order(account, warnings, api_key, shift_start, shift_end, min_per_stop):
    '''Returns:
      -Dict order on success
    Exceptions:
      -requests.RequestException on geocode service error
      -EtapBadDataError on missing or invalid account data
      -GeocodeError on unable to resolve address'''

    if not account.get('address') or not account.get('city'):
        msg = \
          "Routing error: account <strong>%s</strong> missing address/city." % account['id']

        logger.error(msg)
        raise EtapBadDataError(msg)
    else:
        formatted_address = account['address'] + ', ' + account['city'] + ', AB'

    try:
        geo_result = geo.geocode(
            formatted_address,
            api_key,
            postal=account['postalCode']
        )
    except requests.RequestException as e:
        logger.error(str(e))
        raise

    if len(geo_result) == 0:
        msg = \
            "Unable to resolve address <strong>%s, %s</strong>." %(
            account['address'],account['city'])

        logger.error(msg)
        raise GeocodeError(msg)

    geo_result = geo_result[0]

    if 'warning' in geo_result:
        warnings.append(geo_result['warning'])

    return routific.order(
        account,
        formatted_address,
        geo_result,
        shift_start,
        shift_end,
        min_per_stop
    )

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
        logger.error('Error calling api.routific.com/jobs: %s', str(e))
        raise

    task = json.loads(r.text)

    if task['status'] != 'finished':
        return task['status']

    #logger.debug(utils.print_vars(task, depth=5))

    db = get_db()

    route_info = db.routes.find_one({'job_id':job_id})

    output = task['output']
    orders = task['output']['solution'].get(route_info['driver']['name']) or task['output']['solution']['default']

    logger.info(
        '\nJob_id %s: %s\n'\
        'Sorted orders: %s\nUnserved orders: %s\nTravel time: %s',
        job_id, output['status'], len(orders), output['num_unserved'],
        output['total_travel_time'])

    route_length = parse(orders[-1]['arrival_time']) - parse(orders[0]['arrival_time'])

    db['routes'].update_one({'job_id':job_id},
      {'$set': {
          'status':'finished',
          'orders': task['visits'],
          'total_travel_time': output['total_travel_time'],
          'num_unserved': output['num_unserved'],
          'routific': {
              'input': task['input']['visits'],
              'solution': task['output']['solution']
           },
          'duration': route_length.seconds/60
          }})

    if not route_info:
        logger.error("No mongo record for job_id '%s'", job_id)
        return False

    # Routific doesn't include custom fields in the solution object.
    # Copy them over manually.
    # Also create Google Maps url

    for order in orders:
        if order['location_id'] == 'office':
            continue
        elif order['location_id'] == 'depot':
            # TODO: Add proper depot name, phone number, hours, and unload duration

            location = geo.geocode(route_info['end_address'], api_key)[0]['geometry']['location']

            order['customNotes'] = {
                'id': 'depot',
                'name': 'Depot'
            }
            order['gmaps_url'] = geo.get_gmaps_url(
                order['location_name'],
                location['lat'],
                location['lng']
            )
        # Regular order
        else:
            _input = task['input']['visits'][order['location_id']]

            order['customNotes'] = task['input']['visits'][order['location_id']]['customNotes']

            order['gmaps_url'] = geo.get_gmaps_url(
                _input['location']['name'],
                _input['location']['lat'],
                _input['location']['lng']
            )

    conf = db['agencies'].find_one({'name':route_info['agency']})

    # Add office stop
    # TODO: Add travel time from depot to office
    orders.append({
        "location_id":"office",
        "location_name": conf['routing']['locations']['office']['formatted_address'],
        "arrival_time":"",
        "finish_time":"",
        "gmaps_url": conf['routing']['locations']['office']['url'],
        "customNotes": {
            "id": "office",
            "name": conf['routing']['locations']['office']['name']
        }
    })

    return orders

#-------------------------------------------------------------------------------
def is_scheduled(account, route_date):
    # Ignore accounts with Next Pickup > today
    next_pickup = etap.get_udf('Next Pickup Date', account)

    if next_pickup:
        np = next_pickup.split('/')
        next_pickup = parse('/'.join([np[1], np[0], np[2]])).date()

    next_delivery = etap.get_udf('Next Delivery Date', account)

    if next_delivery:
        nd = next_delivery.split('/')
        next_delivery = parse('/'.join([nd[1], nd[0], nd[2]])).date()

    if next_pickup and next_pickup > route_date and not next_delivery:
        return False
    elif next_delivery and next_delivery != route_date and not next_pickup:
        return False
    elif next_pickup and next_delivery and next_pickup > route_date and next_delivery != route_date:
        return False

    return True

#-------------------------------------------------------------------------------
def get_metadata():
    '''Get metadata for routes today and onward
    Return: list of db.routes dicts
    '''

    db = get_db()

    agency = db['users'].find_one({'user': current_user.user_id})['agency']

    today_dt = datetime.combine(date.today(), time())

    routes = db.routes.find({
        'agency': agency,
        'date': {'$gte':today_dt}}).sort('date', 1)

    return routes
