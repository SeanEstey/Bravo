import json
import logging
from dateutil.parser import parse
from datetime import datetime
import requests
import time

from config import *
import etap

from app import info_handler, error_handler, db

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
def get_completed_route(job_id):
    '''Check routific to see if process for job_id is complete.
    Returns list of orders formatted for Google Sheets Route Template
    on success, job status if still processing, False on error
    '''

    r = requests.get('https://api.routific.com/jobs/' + job_id)
    solution = json.loads(r.text)

    if solution['status'] != 'finished':
        return solution['status']

    logger.info('Got solution! Status code: %s', r.status_code)

    route_info = db['routes'].find_one({'job_id':job_id})

    if not route_info:
        logger.error("No mongo record for job_id '%s'", job_id)
        return False

    # Routific doesn't include custom fields in the solution object.
    # Copy them over manually.
    # Also create Google Maps url

    for order in solution['output']['solution'][route_info['driver']]:
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
def geocode(formatted_address, postal=None):
    '''documentation: https://developers.google.com/maps/documentation/geocoding
    formatted_address: string with address + city + province
    Should NOT include postal code
    postal: optional arg. Used to identify correct location when multiple
    results found
    '''

    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {
      'address': formatted_address,
      'key': GOOGLE_API_KEY
    }

    try:
        r = requests.get(url, params=params)
    except Exception as e:
        logger.info('Geocoding exception %s', str(e))
        return False

    response = json.loads(r.text)

    if response['status'] == 'ZERO_RESULTS':
        logger.info("No geocode result for %s", formatted_address)
        return False
    elif response['status'] == 'INVALID_REQUEST':
        logger.info("Improper address %s", formatted_address)
        return False
    elif response['status'] != 'OK':
        logger.info("Error geocoding %s. %s", formatted_address, response)
        return False

    if len(response['results']) == 1 and 'partial_match' in response['results'][0]:
        logger.info('Warning: Only partial match found for "%s". Using "%s". '\
                    'Geo-coordinates may be incorrect.',
                    formatted_address, response['results'][0]['formatted_address'])
    elif len(response['results']) > 1:
        logger.info('Multiple results geocoded for "%s". Finding best match...',
                    formatted_address)

        # No way to identify best match
        if postal is None:
            logger.error('Warning: no postal code provided. Returning first result: "%s"',
                         response['results'][0]['formatted_address'])
            return response['results'][0]

        # Let's use the Postal Code to find the best match
        for idx, result in enumerate(response['results']):
            if not get_postal(result):
                continue

            if get_postal(result)[0:3] == postal[0:3]:
                logger.info('First half of Postal Code "%s" matched in ' \
                            'result[%s]: "%s". Using as best match.',
                            get_postal(result), str(idx), result['formatted_address'])
                return result

        logger.error('Warning: unable to identify correct match. Using first '\
                    'result as best guess: %s',
                    response['results'][0]['formatted_address'])

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
def start_job(block, driver, date, start_address, end_address, etapestry_id):
    '''Use Routific long-running process endpoint.
    Returns: job_id
    '''

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
      "shift_start": "8:00",
      "shift_end": "17:00"
    }

    date = parse(date)
    num_skips = 0

    for account in accounts['data']:
        # Ignore accounts with Next Pickup > today
        next_pickup = etap.get_udf('Next Pickup Date', account)

        if next_pickup:
            np = next_pickup.split('/')
            next_pickup = parse('/'.join([np[1], np[0], np[2]]))

        next_delivery = etap.get_udf('Next Delivery Date', account)

        if next_delivery:
            nd = next_delivery.split('/')
            next_delivery = parse('/'.join([nd[1], nd[0], nd[2]]))

        if next_pickup and next_pickup > date and not next_delivery:
            num_skips += 1
            continue
        elif next_delivery and next_delivery != date and not next_pickup:
            num_skips += 1
            continue
        elif next_pickup and next_delivery and next_pickup > date and next_delivery != date:
            num_skips += 1
            continue

        if account['address'] is None or account['city'] is None:
            logger.error('Missing address or city in account ID %s', account['id'])
            continue

        formatted_address = account['address'] + ', ' + account['city'] + ', AB'

        result = geocode(formatted_address, postal=account['postalCode'])

        if not result:
            continue

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
          "start": "8:00",
          "end": "17:00",
          "duration": 3,
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

        logger.info('job_id: %s', job_id)

        db['routes'].insert_one({
            'job_id': job_id,
            'driver': driver,
            'status': 'processing',
            'block': block,
            'date': date,
            'start_address': start_address,
            'end_address': end_address
            })

        return job_id
    else:
        logger.error('Error retrieving Routific job_id. %s %s',
            r.headers, r.text)
        return False
