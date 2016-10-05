import json
import logging
from dateutil.parser import parse
from oauth2client.client import SignedJwtAssertionCredentials
import httplib2
from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
from datetime import datetime, time, date, timedelta
from time import sleep
import requests
from pymongo import ReturnDocument
import re
import bson.json_util
from flask.ext.login import current_user
from bson import ObjectId

from config import *
import etap
import scheduler
import gdrive
import gsheets

from app import db
logger = logging.getLogger(__name__)

class GeocodeError(Exception):
    pass
class EtapBadDataError(Exception):
    pass


#-------------------------------Stuff Todo---------------------------------------
# TODO: Fix 'office' name on WSF Sheet
# TODO: Add find_depot() code for WSF so routing can move away from Apps Script
# TODO: Test permissions for WSF Sheets. Still errors?
# TODO: Test GeocodeError and EtapBadDataError code paths


#-------------------------------------------------------------------------------
def build_todays_routes():
    '''Route orders for today's Blocks and build Sheets
    '''

    agency = 'vec'
    get_upcoming_routes(agency)

    routes = db['routes'].find({
      'agency': agency,
      'date': datetime.combine(date.today(), time(0,0,0))
    })

    logger.info(
      '%s: -----Building %s routes for %s-----',
      agency, routes.count(), date.today().strftime("%A %b %d"))

    successes = 0
    fails = 0

    for route in routes:
        r = build_route(str(route['_id']))

        if r != True:
            fails += 1
            logger.error('Error building route %s', route['block'])
        else:
            successes += 1

        sleep(2)

    logger.info(
        '%s: -----%s Routes built. %s failures.-----',
        agency, successes, fails)

#-------------------------------------------------------------------------------
def build_route(route_id, job_id=None):
    '''Celery task that routes a Block via Routific and writes orders to a Sheet
    Can take up to a few min to run depending on size of route, speed of
    dependent API services (geocoder, sheets/drive api)
    @route_id: '_id' of record in 'routes' db collection (str)
    @job_id: routific job string. If passed, creates Sheet without re-routing
    Returns: True on success, False on error
    '''

    route = db['routes'].find_one({"_id":ObjectId(route_id)})

    logger.info('%s: Building %s...', route['agency'], route['block'])

    agency_conf = db['agencies'].find_one({'name':route['agency']})

    routing = agency_conf['routing']
    etap_id = agency_conf['etapestry']

    # FIXME. Vec only
    depot = routing['depots'][0]
    driver = routing['drivers'][0]

    # If job_id passed in as arg, skip Routific stage and build spreadsheet
    if job_id is None:
        job_id = submit_job(
            route['block'],
            driver['name'],
            route['date'].isoformat(),
            routing['office_address'],
            depot['formatted_address'],
            etap_id,
            routing['routific']['api_key'],
            min_per_stop = routing['min_per_stop'],
            shift_start = driver['shift_start']
        )

    # Keep looping and sleeping until receive solution or hit
    # CELERYD_TASK_TIME_LIMIT (3000 s)
    orders = get_orders(job_id, agency_conf['google']['geocode']['api_key'])

    if orders == False:
        logger.error('Error retrieving routific solution')
        return False

    while orders == "processing":
        logger.debug('No solution yet. Sleeping 5s...')
        sleep(5)
        orders = get_orders(job_id, agency_conf['google']['geocode']['api_key'])

    # Build the Google Sheet and copy orders

    oauth = db['agencies'].find_one({'name':route['agency']})['google']['oauth']

    ss_id = create_sheet(
        route['agency'],
        gdrive.gauth(oauth),
        route['block'])

    write_orders(
        gsheets.gauth(oauth),
        ss_id,
        orders)

    db['routes'].update_one({'job_id':job_id},{'$set':{'ss_id':ss_id}})

    logger.info(
        '%s Sheet created. Orders written.', route['block'])

    return True

#-------------------------------------------------------------------------------
def build_order(account, warnings, api_key, shift_start, shift_end, min_per_stop):
    '''Returns:
      -Dict order on success
    Exceptions:
      -requests.RequestException on geocode service error
      -EtapBadDataError on missing or invalid account data
      -GeocodeError on unable to resolve address'''

    if not account.get('address') or not account.get('city'):
        msg = "Routing error: account %s missing address and/or city" % account['id']
        logger.error(msg)
        raise EtapBadDataError(msg)
    else:
        formatted_address = account['address'] + ', ' + account['city'] + ', AB'

    try:
        result = geocode(formatted_address, api_key, postal=account['postalCode'])[0]
    except requests.RequestException as e:
        logger.error(str(e))
        raise

    if len(result) == 0:
        msg = "Unable to resolve address: %s, %s" % (account['address'],account['city'])
        logger.error(msg)
        raise GeocodeError(msg)

    if 'warning' in result:
        warnings.append(result['warning'])

    return {
      "location": {
        "name": formatted_address,
        "lat": result['geometry']['location']['lat'],
        "lng": result['geometry']['location']['lng']
      },
      "start": shift_start,
      "end": shift_end,
      "duration": min_per_stop,
      "customNotes": {
        "id": account['id'],
        "name": account['name'],
        "phone": etap.get_primary_phone(account),
        "email": 'Yes' if account.get('email') else 'No',
        "contact": etap.get_udf('Contact', account),
        "block": etap.get_udf('Block', account),
        "status": etap.get_udf('Status', account),
        "neighborhood": etap.get_udf('Neighborhood', account),
        "driver notes": etap.get_udf('Driver Notes', account),
        "office notes": etap.get_udf('Office Notes', account),
        "next pickup": etap.get_udf('Next Pickup Date', account)
      }
    }

#-------------------------------------------------------------------------------
def get_orders(job_id, api_key):
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

    logger.debug(r.text)

    route_info = db['routes'].find_one({'job_id':job_id})

    output = task['output']
    orders = task['output']['solution'][route_info['driver']]

    logger.info(
        '\nJob_id %s: %s\n'\
        'Sorted orders: %s\nUnserved orders: %s\nTravel time: %s',
        job_id, output['status'], len(orders), output['num_unserved'],
        output['total_travel_time'])

    # TODO: Include trip time back to office for WSF
    route_length = parse(orders[-1]['arrival_time']) - parse(orders[0]['arrival_time'])

    db['routes'].update_one({'job_id':job_id},
      {'$set': {
          'status':'finished',
          'orders': task['visits'],
          'total_travel_time': output['total_travel_time'],
          'num_unserved': output['num_unserved'],
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

            location = geocode(route_info['end_address'], api_key)[0]['geometry']['location']

            order['customNotes'] = {
                'id': 'depot',
                'name': 'Depot'
            }
            order['gmaps_url'] = get_gmaps_url(
                order['location_name'],
                location['lat'],
                location['lng']
            )
        # Regular order
        else:
            _input = task['input']['visits'][order['location_id']]

            order['customNotes'] = task['input']['visits'][order['location_id']]['customNotes']

            order['gmaps_url'] = get_gmaps_url(
                _input['location']['name'],
                _input['location']['lat'],
                _input['location']['lng']
            )

    conf = db['agencies'].find_one({'name':route_info['agency']})

    # Add office stop
    # TODO: Add travel time from depot to office
    orders.append({
        "location_id":"office",
        "location_name": conf['routing']['office']['formatted_address'],
        "arrival_time":"",
        "finish_time":"",
        "gmaps_url": conf['routing']['office']['url'],
        "customNotes": {
            "id": "office",
            "name": conf['routing']['office']['name']
        }
    })

    return orders

#-------------------------------------------------------------------------------
def submit_job(block, driver, date, start_address, end_address, etapestry_id,
    routific_key, min_per_stop=3, shift_start="08:00", shift_end="19:00"):
    '''Submit orders to Routific via asynchronous long-running process endpoint
    API reference: https://docs.routific.com/docs/api-reference
    @date: string format 'Sat Sep 10 2016'
    Returns:
      -String job_id on success
      -False on error'''

    accounts = get_accounts(block, etapestry_id)['data']

    api_key = db['agencies'].find_one({'name':etapestry_id['agency']})['google']['geocode']['api_key']

    start = geocode(start_address, api_key)[0]['geometry']['location']
    end = geocode(end_address, api_key)[0]['geometry']['location']

    payload = {
      "visits": {},
      "fleet": {
        driver: {
          "start_location": {
            "id": "office",
            "lat": start['lat'],
            "lng": start['lng'],
            "name": start_address,
           },
          "end_location": {
            "id": "depot",
            "lat": end['lat'],
            "lng": end['lng'],
            "name": end_address,
          },
          "shift_start": shift_start,
          "shift_end": shift_end
        }
      },
      "options": {
        # TODO: experiment with this
        # 'traffic': ['faster' (default), 'fast', 'normal', 'slow', 'very slow']
        "traffic": "slow",
        "shortest_distance": True
      }
    }

    route_date = parse(date).date()
    num_skips = 0

    warnings = []
    errors = []

    # Build the orders for Routific
    for account in accounts:
        if is_scheduled(account, route_date) == False:
            num_skips += 1
            continue

        try:
            order = build_order(
                account, warnings, api_key, shift_start, shift_end, min_per_stop
            )
        except EtapBadDataError as e:
            errors.append(str(e))
            continue
        except GeocodeError as e:
            errors.append(str(e))
            continue
        except requests.RequestException as e:
            errors.append(str(e))
            continue

        if order == False:
            num_skips += 1
        else:
            payload['visits'][account['id']] = order

    logger.debug('Omitting %s no pickups', str(num_skips))

    try:
        r = requests.post(
            'https://api.routific.com/v1/vrp-long',
            headers = {
              'content-type': 'application/json',
              'Authorization': routific_key
            },
            data=json.dumps(payload)
        )
    except Exception as e:
        logger.error('Routific exception %s', str(e))
        return False

    if r.status_code != 202:
        logger.error('Error retrieving Routific job_id. %s %s',
            r.headers, r.text)
        return False

    job_id = json.loads(r.text)['job_id']

    logger.info(
        '\nSubmitted routific task\n'\
        'Job_id: %s\nOrders: %s\nStart: %s\nEnd: %s\n'\
        'Min/stop: %s\nTraffic: %s',
        job_id, len(payload['visits']), shift_start,
        shift_end, min_per_stop, payload['options']['traffic'])

    # Save route info with job_id to DB



    existing_job = db['routes'].find_one({
      'agency': etapestry_id['agency'],
      'block': block,
      'date': datetime.combine(route_date, time(0,0,0))
    })

    db['routes'].update_one(
        existing_job,
        {'$set': {
            'agency': etapestry_id['agency'],
            'job_id': job_id,
            'driver': driver,
            'traffic': payload['options']['traffic'],
            'status': 'processing',
            'block': block,
            'block_size': len(accounts),
            'orders': len(payload['visits']),
            'no_pickups': num_skips,
            'date': datetime.combine(route_date, time(0,0,0)),
            'start_address': start_address,
            'end_address': end_address,
            'geocode_warnings': warnings,
            'geocode_errors': errors
        }})

    return job_id

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
def get_upcoming_routes(agency):
    '''Get list of scheduled routes for next X days.
    Pullled from db['routes']. Document is inserted for a Block if
    not already in collection.
    Return: list of db['routes'] documents
    '''

    # send today's Blocks routing status
    today_dt = datetime.combine(date.today(), time())

    #agency = db['users'].find_one({'user': current_user.username})['agency']

    cal_ids = db['agencies'].find_one({'name':agency})['cal_ids']
    oauth = db['agencies'].find_one({'name':agency})['google']['oauth']

    end_dt = today_dt + timedelta(days=5)

    events = []

    for id in cal_ids:
        events += scheduler.get_cal_events(cal_ids[id], today_dt, end_dt, oauth)

    events = sorted(events, key=lambda k: k['start']['date'])

    routes = []

    for event in events:
        # yyyy-mm-dd format
        event_dt = parse(event['start']['date'])

        block = re.match(r'^((B|R)\d{1,2}[a-zA-Z]{1})', event['summary']).group(0)

        # 1. Do we already have this Block in Routes collection?
        route = db['routes'].find_one({'date':event_dt, 'block': block, 'agency':agency})

        if route is None:
            # 1.a Let's grab info from eTapestry
            etap_info = db['agencies'].find_one({'name':agency})['etapestry']

            try:
                a = etap.call(
                  'get_query_accounts',
                  etap_info,
                  {'query':block, 'query_category':etap_info['query_category']}
                )
            except Exception as e:
                logger.error('Error retrieving accounts for query %s', block)

            if 'count' not in a:
                logger.error('No accounts found in query %s', block)
                continue

            num_dropoffs = 0
            num_booked = 0

            event_d = event_dt.date()

            for account in a['data']:
                npu = etap.get_udf('Next Pickup Date', account)

                if npu == '':
                    continue

                npu_d = etap.ddmmyyyy_to_date(npu)

                if npu_d == event_d:
                    num_booked += 1

                if etap.get_udf('Status', account) == 'Dropoff':
                    num_dropoffs += 1

            _route = {
              'agency': agency,
              'date': event_dt,
              'block': block,
              'status': 'pending',
              'orders': num_booked,
              'block_size': len(a['data']),
              'dropoffs': num_dropoffs
            }

            db['routes'].insert_one(_route)

            routes.append(_route)

            logger.info('Inserting route %s', bson.json_util.dumps(routes[-1]))

        else:
            # 2. Get updated order count from reminders job
            job = db['jobs'].find_one({'name':block, 'agency':agency})

            if job is not None:
                num_reminders = db['reminders'].find({'job_id':job['_id']}).count()
                orders = num_reminders - job['no_pickups']

                db['routes'].update_one(
                  {'date':event_dt, 'agency':agency},
                  {'$set':{'orders':orders}})

            routes.append(route)

    return routes

#-------------------------------------------------------------------------------
def get_gmaps_url(address, lat, lng):
    base_url = 'https://www.google.ca/maps/place/'

    # TODO: use proper urlencode() function here
    full_url = base_url + address.replace(' ', '+')

    full_url +=  '/@' + str(lat) + ',' + str(lng)
    full_url += ',17z'

    return full_url

#-------------------------------------------------------------------------------
def get_postal(geo_result):
    for component in geo_result['address_components']:
        if 'postal_code' in component['types']:
            return component['short_name']

    return False

#-------------------------------------------------------------------------------
def geocode(address, api_key, postal=None, raise_exceptions=False):
    '''Finds best result from Google geocoder given address
    API Reference: https://developers.google.com/maps/documentation/geocoding
    @address: string with address + city + province. Should NOT include postal code.
    @postal: optional arg. Used to identify correct location when multiple
    results found
    Returns:
      -Success: single element list containing result (dict)
      -Empty list [] no result
    Exceptions:
      -Raises requests.RequestException on connection error'''

    try:
        response = requests.get(
          'https://maps.googleapis.com/maps/api/geocode/json',
          params = {
            'address': address,
            'key': api_key
          })
    except requests.RequestException as e:
        logger.error(str(e))
        raise

    logger.debug(response.text)

    response = json.loads(response.text)

    if response['status'] == 'ZERO_RESULTS':
        e = 'Error: No geocode result for ' + address
        logger.error(e)
        return []
    elif response['status'] == 'INVALID_REQUEST':
        e = 'Error: Invalid request for ' + address
        logger.error(e)
        return []
    elif response['status'] != 'OK':
        e = 'Error: Could not geocode ' + address
        logger.error(e)
        return []

    # Single result

    if len(response['results']) == 1:
        if 'partial_match' in response['results'][0]:
            warning = 'Warning: partial match for "%s". Using "%s"' %\
                      (address, response['results'][0]['formatted_address'])

            response['results'][0]['warning'] = warning
            logger.debug(warning)

        return response['results']

    # Multiple results

    if postal is None:
        # No way to identify best match. Return 1st result (best guess)
        response['results'][0]['warning'] = 'Warning: multiple results for "%s". '\
          'No postal code. Using 1st result "%s"' % (
          address, response['results'][0]['formatted_address'])

        logger.debug(response['results'][0]['warning'])

        return [response['results'][0]]
    else:
        # Let's use the Postal Code to find the best match
        for idx, result in enumerate(response['results']):
            if not get_postal(result):
                continue

            if get_postal(result)[0:3] == postal[0:3]:
                result['warning'] = \
                  'Warning: multiple results for "%s". First half of Postal Code "%s" matched in ' \
                  'result[%s]: "%s". Using as best match.' % (
                  address, get_postal(result), str(idx), result['formatted_address'])

                logger.debug(result['warning'])

                return [result]

            # Last result and still no Postal match.
            if idx == len(response['results']) -1:
                response['results'][0]['warning'] = \
                  'Warning: multiple results for "%s". No postal code match. '\
                  'Using "%s" as best guess.' % (
                  address, response['results'][0]['formatted_address'])

                logger.error(response['results'][0]['warning'])

    return [response['results'][0]]

#-------------------------------------------------------------------------------
def get_accounts(block, etapestry_id):
    # Get data from route via eTap API
    accounts = etap.call('get_query_accounts', etapestry_id, {
      "query": block,
      "query_category": etapestry_id['query_category']
    })

    return accounts

#-------------------------------------------------------------------------------
def create_sheet(agency, drive_api, title):
    '''Makes copy of Route Template, add edit/owner permissions
    IMPORTANT: Make sure 'Routed' folder has edit permissions for agency
    service account.
    IMPORTANT: Make sure route template file has edit permissions for agency
    service account.
    Uses batch request for creating permissions
    Returns: ID of new Sheet file
    '''

    conf = db['agencies'].find_one({'name':agency})['routing']['gdrive']

    # Copy Route Template
    file_copy = drive_api.files().copy(
      fileId = conf['template_sheet_id'],
      body = {
        'name': title
      }
    ).execute()

    # Prevent 500 errors
    sleep(2)

    # Transfer ownership permission, add writer permissions
    gdrive.add_permissions(drive_api, file_copy['id'], conf['permissions'])

    logger.debug('Permissions added')

    try:
        # Retrieve the existing parents to remove
        file = drive_api.files().get(
          fileId=file_copy['id'],
          fields='parents').execute()
    except Exception as e:
        logger.error('Error listing files: %s', str(e))
        return False

    previous_parents = ",".join(file.get('parents'))

    try:
        # Move the file to the new folder
        file = drive_api.files().update(
          fileId=file_copy['id'],
          addParents = conf['routed_folder_id'],
          removeParents=previous_parents,
          fields='id, parents').execute()
    except Exception as e:
        logger.error('Error moving to folder: %s', str(e))
        return False

    logger.debug('sheet_id %s created', file_copy['id'])

    return file_copy['id']

#-------------------------------------------------------------------------------
def write_orders(sheets_api, ss_id, orders):
    '''Write formatted orders to route sheet.
    order: {
        "location_id": etapestry account or ['depot', 'office'],
        "location_name":"21 Arbour Crest Close NW, Calgary, AB",
        "arrival_time":"09:11",
        "finish_time":"09:15",
        "gmaps_url": url,
        "customNotes": {
            "id": etapestry id for order or ['depot', 'office'],
            "name": account name,
            "contact": contat person (businesses),
            "block": blocks,
            "status": etapestry status,
            "neighborhood": (optional),
            "driver notes": (optional),
            "office notes": (optional),
            "next pickup": date string
        }
    }'''

    rows = []
    cells_to_bold = []

    # Chop off office start_address
    orders = orders[1:]

    for idx in range(len(orders)):
        order = orders[idx]

        addy = order['location_name'].split(', ');

        # Remove Postal Code from Google Maps URL label
        if re.match(r'^T\d[A-Z]$', addy[-1]) or re.match(r'^T\d[A-Z]\s\d[A-Z]\d$', addy[-1]):
           addy.pop()

        formula = '=HYPERLINK("' + order['gmaps_url'] + '","' + ", ".join(addy) + '")'

        '''Info Column format (column D):

        Notes: Fri Apr 22 2016: Pickup Needed
        Name: Cindy Borsje

        Neighborhood: Lee Ridge
        Block: R10Q,R8R
        Contact (business only): James Schmidt
        Phone: 780-123-4567
        Email: Yes/No'''

        order_info = ''

        if order['location_id'] == 'depot':
            order_info += 'Name: Depot\n'
            order_info += '\nArrive: ' + order['arrival_time']
        elif order['location_id'] == 'office':
            order_info += 'Name: ' + order['customNotes']['name']+ '\n'
            order_info += '\nArrive: ' + order['arrival_time']
        # Regular order
        else:
            if order['customNotes'].get('driver notes'):
                # Row = (order idx + 1) + 1 (header)
                cells_to_bold.append([idx+1+1, 4])

                order_info += 'NOTE: ' + order['customNotes']['driver notes'] +'\n\n'

                if order['customNotes']['driver notes'].find('***') > -1:
                    order_info = order_info.replace("***", "")

            order_info += 'Name: ' + order['customNotes']['name'] + '\n'

            if order['customNotes'].get('neighborhood'):
              order_info += 'Neighborhood: ' + order['customNotes']['neighborhood'] + '\n'

            order_info += 'Block: ' + order['customNotes']['block']

            if order['customNotes'].get('contact'):
              order_info += '\nContact: ' + order['customNotes']['contact']
            if order['customNotes'].get('phone'):
              order_info += '\nPhone: ' + order['customNotes']['phone']
            if order['customNotes'].get('email'):
              order_info += '\nEmail: ' + order['customNotes']['email']

            order_info += '\nArrive: ' + order['arrival_time']

        rows.append([
          formula,
          '',
          '',
          order_info,
          order['customNotes'].get('id') or '',
          order['customNotes'].get('driver notes') or '',
          order['customNotes'].get('block') or '',
          order['customNotes'].get('neighborhood') or '',
          order['customNotes'].get('status') or '',
          order['customNotes'].get('office notes') or ''
        ])

    # Start from Row 2 Column A to Column J
    _range = "A2:J" + str(len(orders)+1)

    gsheets.write_rows(sheets_api, ss_id, rows, _range)

    gsheets.vert_align_cells(sheets_api, ss_id, 2, len(orders)+1, 1,1)

    gsheets.bold_cells(sheets_api, ss_id, cells_to_bold)

    values = gsheets.get_values(sheets_api, ss_id, "A1:$A")

    hide_start = 1 + len(rows) + 1;
    hide_end = values.index(['***Route Info***'])

    gsheets.hide_rows(sheets_api, ss_id, hide_start, hide_end)
