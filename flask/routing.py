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

from config import *
import etap
import scheduler

from app import info_handler, error_handler, debug_handler, db
from tasks import celery_app

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.addHandler(debug_handler)
logger.setLevel(logging.DEBUG)


#-------------------------------------------------------------------------------
def get_upcoming_routes():
    '''Get list of scheduled routes for next X days.
    Pullled from db['routes']. Document is inserted for a Block if
    not already in collection.
    Return: list of db['routes'] documents
    '''

    # send today's Blocks routing status
    today_dt = datetime.combine(date.today(), time())

    agency = db['users'].find_one({'user': current_user.username})['agency']

    cal_ids = db['agencies'].find_one({'name':agency})['cal_ids']
    oauth = db['agencies'].find_one({'name':agency})['oauth']

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

            routes.append({
              'agency': agency,
              'date': event_dt,
              'block': block,
              'status': 'pending',
              'orders': num_booked,
              'block_size': len(a['data']),
              'duration': 0,
              'dropoffs': num_dropoffs
            })

            logger.info('Inserting route %s', bson.json_util.dumps(routes[-1]))

            db['routes'].insert_one(routes[-1])
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
@celery_app.task
def build_route(agency, block, date_str):
    '''Check on a scheduled route if job_id not know.
    @date_str: string format 'Sat Sep 10 2016'
    Returns: see get_completed_route()
    '''

    routific = db['agencies'].find_one({'name':agency})['routific']
    etap_id = db['agencies'].find_one({'name':agency})['etapestry']

    logger.info("Building %s %s %s", agency, block, date_str)

    job_id = start_job(
        block,
        'driver',
        date_str,
        routific['start_address'],
        routific['end_address'],
        etap_id,
        min_per_stop = routific['min_per_stop'],
        shift_start = routific['shift_start']
    )

    # Keep looping and sleeping until receive solution or hit
    # CELERYD_TASK_TIME_LIMIT (3000 s)

    # TODO: Change this func to return entire solution to check status, not
    # just orders
    orders = get_completed_route(job_id)

    if orders == False:
        logger.error('Error retrieving routific solution')
        return False

    while orders == "processing":
        logger.info('No solution yet. Sleeping 5s...')

        sleep(5)

        orders = get_completed_route(job_id)

    drive_api = auth_gservice(agency, 'drive')
    sheet_id = create_sheet(agency, drive_api, block)

    sheets_api = auth_gservice(agency, 'sheets')
    write_orders(sheets_api, sheet_id, orders)

    db['routes'].update_one({'job_id':job_id},{'$set':{'ss_id':sheet_id}})

    logger.info('Route %s complete.', block)

    return True


#-------------------------------------------------------------------------------
def get_completed_route(job_id):
    '''Check routific to see if process for job_id is complete.
    Return: Routific 'solution' dict with orders on success, job status code
    on incomplete, and False on error.
    '''

    r = requests.get('https://api.routific.com/jobs/' + job_id)
    solution = json.loads(r.text)

    logger.debug(solution)

    if solution['status'] != 'finished':
        return solution['status']

    logger.info(
      'Job_ID \'%s\' finished. Returning sorted orders (Status code: %s)',
      job_id, r.status_code)

    route_info = db['routes'].find_one({'job_id':job_id})

    orders = solution['output']['solution'][route_info['driver']]

    # TODO: Include trip time back to office for WSF
    route_length = parse(orders[-1]['arrival_time']) - parse(orders[0]['arrival_time'])

    db['routes'].update_one({'job_id':job_id},
      {'$set': {
          'status':'finished',
          'orders': solution['visits'],
          'duration': route_length.seconds/60
          }})

    if not route_info:
        logger.error("No mongo record for job_id '%s'", job_id)
        return False

    # Routific doesn't include custom fields in the solution object.
    # Copy them over manually.
    # Also create Google Maps url

    for order in orders:
        id = order['location_id']

        if id == 'depot':
            location = geocode(route_info['end_address'])['geometry']['location']

            order['gmaps_url'] = get_gmaps_url(
                order['location_name'],
                location['lat'],
                location['lng']
            )
            continue

        if id in solution['input']['visits']:
            order['customNotes'] = solution['input']['visits'][id]['customNotes']

            order['gmaps_url'] = get_gmaps_url(
                order['location_name'],
                order['customNotes']['lat'],
                order['customNotes']['lng']
            )

    return solution['output']['solution'][route_info['driver']]

#-------------------------------------------------------------------------------
def start_job(block, driver, date, start_address, end_address, etapestry_id,
        min_per_stop=3, shift_start="08:00", shift_end="19:00"):
    '''Use Routific long-running process endpoint.
    @date: string format 'Sat Sep 10 2016'
    Returns: job_id
    '''

    logger.info('Submitting Routific job for %s: start "%s", end "%s", %s min/stop',
                block, shift_start, shift_end, str(min_per_stop))

    accounts = get_accounts(block, etapestry_id)

    start = geocode(start_address)['geometry']['location']
    end = geocode(end_address)['geometry']['location']

    payload = {
      "visits": {},
      "fleet": {}
    }

    payload["fleet"][driver] = {
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

    route_date = parse(date).date()
    num_skips = 0

    geocode_warnings = []

    for account in accounts['data']:
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
            num_skips += 1
            continue
        elif next_delivery and next_delivery != route_date and not next_pickup:
            num_skips += 1
            continue
        elif next_pickup and next_delivery and next_pickup > route_date and next_delivery != route_date:
            num_skips += 1
            continue

        if account['address'] is None or account['city'] is None:
            logger.error('Missing address or city in account ID %s', account['id'])
            continue

        formatted_address = account['address'] + ', ' + account['city'] + ', AB'

        result = geocode(formatted_address, postal=account['postalCode'])

        if not result:
            logger.info(
              'Omitting Account %s from route due to geocode error',
              account['id'])
            continue

        if 'warning' in result:
            geocode_warnings.append(result['warning'])

        coords = {}

        if 'partial_match' in result and etap.get_udf('lat', account):
            logger.info('Retrieved lat/lng from account %s', account['id'])

            coords['lat'] = etap.get_udf('lat', account)
            coords['lng'] = etap.get_udf('lng', account)
        else:
            coords = result['geometry']['location']

        payload['visits'][account['id']] = { # location_id
          "location": {
            "name": formatted_address,
            "lat": coords['lat'],
            "lng": coords['lng']
          },
          "start": shift_start,
          "end": shift_end,
          "duration": min_per_stop,
          "customNotes": {
            "lat": coords['lat'],
            "lng": coords['lng'],
            "id": account['id'],
            "name": account['name'],
            "contact": etap.get_udf('Contact', account),
            "block": etap.get_udf('Block', account),
            "status": etap.get_udf('Status', account),
            "neighborhood": etap.get_udf('Neighborhood', account),
            "driver notes": etap.get_udf('Driver Notes', account),
            "office notes": etap.get_udf('Office Notes', account),
            "next pickup": etap.get_udf('Next Pickup Date', account)
          }
        }

        if account['phones']:
            for phone in account['phones']:
                if phone['type'] == 'Mobile' or phone['type'] == 'Cell':
                    payload['visits'][account['id']]['customNotes']['phone'] = \
                    phone['number'] + ' (Mobile)'
                    break
                else:
                    payload['visits'][account['id']]['customNotes']['phone'] = \
                    phone['number'] + ' (' + phone['type'] + ')'

        if account['email']:
            payload['visits'][account['id']]['customNotes']['email'] = 'Yes'
        else:
            payload['visits'][account['id']]['customNotes']['email'] = 'No'

    logger.info('Skipping %s no pickups', str(num_skips))

    try:
        r = requests.post(
            'https://api.routific.com/v1/vrp-long',
            headers = {
              'content-type': 'application/json',
              'Authorization': ROUTIFIC_KEY
            },
            data=json.dumps(payload)
        )
    except Exception as e:
        logger.error('Routific exception %s', str(e))
        return False

    if r.status_code == 202:
        job_id = json.loads(r.text)['job_id']

        existing_job = db['routes'].find_one({
          'agency': etapestry_id['agency'],
          'block': block,
          'date': datetime.combine(route_date, time(0,0,0))
        })

        job_info = {
            'agency': etapestry_id['agency'],
            'job_id': job_id,
            'driver': driver,
            'status': 'processing',
            'block': block,
            'block_size': len(accounts),
            'orders': len(accounts) - num_skips,
            'date': datetime.combine(route_date, time(0,0,0)),
            'start_address': start_address,
            'end_address': end_address,
            'geocode_warnings': geocode_warnings
        }

        if existing_job:
            logger.info(
              '%s: Routific job already exists for Block % on %s. Over-writing.',
              etapestry_id['agency'], block, route_date.strftime('%b %d'))

            db['routes'].update_one(existing_job, {'$set':job_info})
        else:
            db['routes'].insert_one(job_info)

            logger.info(
              '%s: Routific job started for Block %s (Job_ID: %s)',
              etapestry_id['agency'], block, job_id)

        return job_id
    else:
        logger.error('Error retrieving Routific job_id. %s %s',
            r.headers, r.text)
        return False


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
def geocode(address, postal=None, save_warnings_to=None):
    '''documentation: https://developers.google.com/maps/documentation/geocoding
    @address: string with address + city + province. Should NOT include postal code.
    @postal: optional arg. Used to identify correct location when multiple
    results found
    Returns: geocode result (dict), False on error
    '''

    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {
      'address': address,
      'key': GOOGLE_API_KEY
    }

    try:
        r = requests.get(url, params=params)
    except Exception as e:
        logger.error('Geocoding exception %s', str(e))
        return False

    response = json.loads(r.text)

    if response['status'] == 'ZERO_RESULTS':
        logger.error("No geocode result for %s", address)
        return False
    elif response['status'] == 'INVALID_REQUEST':
        logger.error("Improper address %s", address)
        return False
    elif response['status'] != 'OK':
        logger.error("Error geocoding %s. %s", address, response)
        return False

    if len(response['results']) == 1 and 'partial_match' in response['results'][0]:
        response['results'][0]['warning'] = 'Warning: partial match for "%s". Using "%s"' % (
        address, response['results'][0]['formatted_address'])

        logger.info(response['results'][0]['warning'])
    elif len(response['results']) > 1:
        if postal is None:
            # No way to identify best match
            response['results'][0]['warning'] = 'Warning: multiple results for "%s". '\
              'No postal code. Using 1st result "%s"' % (
              address, response['results'][0]['formatted_address'])

            logger.info(response['results'][0]['warning'])

            return response['results'][0]

        # Let's use the Postal Code to find the best match
        for idx, result in enumerate(response['results']):
            if not get_postal(result):
                continue

            if get_postal(result)[0:3] == postal[0:3]:
                result['warning'] = \
                  'Warning: multiple results for "%s". First half of Postal Code "%s" matched in ' \
                  'result[%s]: "%s". Using as best match.' % (
                  address, get_postal(result), str(idx), result['formatted_address'])

                logger.info(result['warning'])

                return result

        response['results'][0]['warning'] = \
          'Warning: multiple results for "%s". No postal code match. '\
          'Using "%s" as best guess.' % (
          address, response['results'][0]['formatted_address'])

        logger.error(response['results'][0]['warning'])

    return response['results'][0]

#-------------------------------------------------------------------------------
def get_accounts(block, etapestry_id):
    # Get data from route via eTap API
    accounts = etap.call('get_query_accounts', etapestry_id, {
      "query": block,
      "query_category": etapestry_id['query_category']
    })

    return accounts

#-------------------------------------------------------------------------------
def auth_gservice(agency, name):
    if name == 'sheets':
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        version = 'v4'
    elif name == 'drive':
        scope = ['https://www.googleapis.com/auth/drive',
         'https://www.googleapis.com/auth/drive.file']
        version = 'v3'
    elif name == 'calendar':
       scope = ['https://www.googleapis.com/auth/calendar.readonly']
       version = 'v3'

    oauth = db['agencies'].find_one({'name': agency})['oauth']

    try:
        credentials = SignedJwtAssertionCredentials(
            oauth['client_email'],
            oauth['private_key'],
            scope
        )

        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build(name, version, http=http)
    except Exception as e:
        logger.error('Error authorizing %s: %s', name, str(e))
        return False

    logger.info('%s api authorized', name)
    print('%s api authorized', name)

    return service

#-------------------------------------------------------------------------------
def create_sheet(agency, drive_api, title):
    '''Make copy of Route Template, add edit/owner permissions
    Uses batch request for creating permissions
    Returns: ID of new Sheet file
    '''

    template_id = db['agencies'].find_one({'name':agency})['routing']['gdrive_template_id']

    # Copy Route Template
    file_copy = drive_api.files().copy(
      fileId=template_id,
      body={
        'name': title
      }
    ).execute()

    print file_copy

    routed_folder_id = db['agencies'].find_one({'name':agency})['routing']['routed_folder_id']

    # Retrieve the existing parents to remove
    file = drive_api.files().get(
      fileId=file_copy['id'],
      fields='parents').execute()

    previous_parents = ",".join(file.get('parents'))

    # Move the file to the new folder
    file = drive_api.files().update(
      fileId=file_copy['id'],
      addParents=routed_folder_id,
      removeParents=previous_parents,
      fields='id, parents').execute()

    return file_copy['id']


#-------------------------------------------------------------------------------
def write_orders(sheets_api, ss_id, orders):
    '''Write the routed orders to the route sheet
    '''

    rows = []

    orders = orders[1:-1]

    num_orders = len(orders)

    for order in orders:
        addy = order['location_name'].split(', ');

        # Remove Postal Code from Google Maps URL label
        if re.match(r'^T\d[A-Z]$', addy[-1]) or re.match(r'^T\d[A-Z]\s\d[A-Z]\d$', addy[-1]):
           addy.pop()

        formula = '=HYPERLINK("' + order['gmaps_url'] + '","' + ", ".join(addy) + '")'

        '''
        Info Column format (column D):

        Notes: Fri Apr 22 2016: Pickup Needed
        Name: Cindy Borsje

        Neighborhood: Lee Ridge
        Block: R10Q,R8R
        Contact (business only): James Schmidt
        Phone: 780-123-4567
        Email: Yes/No
        '''

        order_info = ''

        if order['customNotes'].get('driver notes'):
          order_info += 'NOTE: ' + order['customNotes']['driver notes'] + '\n\n'

          #sheet.getRange(i+2, headers.indexOf('Order Info')+1).setFontWeight("bold");

          if order['customNotes']['driver notes'].find('***') > -1:
            order_info = order_info.replace("***", "")
            #sheet.getRange(i+2, headers.indexOf('Order Info')+1).setFontColor("red");

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
    _range = "A2:J" + str(num_orders+1)

    write_rows(sheets_api, ss_id, rows, _range)

    values = get_values(sheets_api, ss_id, "A1:$A")

    hide_start = 1 + len(rows) + 1;
    hide_end = values.index(['***Route Info***'])

    hide_rows(sheets_api, ss_id, hide_start, hide_end)


#-------------------------------------------------------------------------------
def write_rows(sheets_api, ss_id, rows, a1_range):
    sheets_api.spreadsheets().values().update(
      spreadsheetId = ss_id,
      valueInputOption = "USER_ENTERED",
      range = a1_range,
      body = {
        "majorDimension": "ROWS",
        "values": rows
      }
    ).execute()


#-------------------------------------------------------------------------------
def get_values(sheets_api, ss_id, a1_range):
    values = sheets_api.spreadsheets().values().get(
      spreadsheetId = ss_id,
      range=a1_range
    ).execute()

    return values['values']


#-------------------------------------------------------------------------------
def hide_rows(sheets_api, ss_id, start, end):
    '''
    @start: inclusive row
    @end: inclusive row
    '''
    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId = ss_id,
        body = {
            'requests': {
                'updateDimensionProperties': {
                    'fields': '*',
                    'range': {
                        'startIndex': start-1,
                        'endIndex': end,
                        'dimension': 'ROWS'
                    },
                    'properties': {
                        'hiddenByUser': True
                    }
                }
            }
        }
    ).execute()
