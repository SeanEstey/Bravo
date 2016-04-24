import json
import requests
import time

from config import *
import etap

from app import log_handler

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)

#-------------------------------------------------------------------------------
def get_sorted_orders(form):
    # TODO: Test arguments

    job_id = get_job_id(form['block'], form['driver'], form['start_addy'], form['end_addy'])

    solution = get_solution(job_id)

    # Routific doesn't include custom fields in the solution object.
    # Copy them over manually.
    # Also create Google Maps url

    for order in solution['output']['solution'][form['driver']]:
        id = order['location_id']

        if id == 'depot':
            location = geocode(form['end_addy'])['geometry']['location']

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

    return solution['output']['solution'][form['driver']]

#-------------------------------------------------------------------------------
def get_gmaps_url(address, lat, lng):
    base_url = 'https://www.google.ca/maps/place/'

    # TODO: use proper urlencode() function here
    full_url = base_url + address.replace(' ', '+')

    full_url +=  '/@' + str(lat) + ',' + str(lng)
    full_url += ',17z'

    return full_url

#-------------------------------------------------------------------------------
def geocode(address):
    '''documentation: https://developers.google.com/maps/documentation/geocoding
    Returns first result
    Note: including Postal Code in address seems to lower accuracy of results
    '''

    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {
      'address': address,
      'key': GOOGLE_API_KEY
    }

    try:
        r = requests.get(url, params=params)
    except Exception as e:
        logger.info('Geocoding exception %s', str(e))
        return False

    response = json.loads(r.text)

    if len(response['results']) > 0 and 'partial_match' in response['results'][0]:
        logger.info('Partial match found for "%s". First match is most likely to be correct: "%s"',
                    address, response['results'][0]['formatted_address'])

    if len(response['results']) > 1:
        logger.info('Multiple results geocoded for "%s". Returning first result: "%s"',
                    address, response['results'][0]['formatted_address'])

    if response['status'] == 'ZERO_RESULTS':
        logger.info("No geocode result for %s", address)
        return False
    elif response['status'] == 'INVALID_REQUEST':
        logger.info("Improper address %s", address)
        return False
    elif response['status'] != 'OK':
        logger.info("Error geocoding %s. %s", address, response)
        return False

    return response['results'][0]

#-------------------------------------------------------------------------------
def get_accounts(block):
    # Get data from route via eTap API
    accounts = etap.call('get_query_accounts', ETAP_WRAPPER_KEYS, {
      "query": block,
      "query_category": "ETW: Routes"
    })

    return accounts

#-------------------------------------------------------------------------------
def get_solution(job_id):
    r = requests.get('https://api.routific.com/jobs/' + job_id)

    data = json.loads(r.text)

    while data['status'] != 'finished':
        logger.info('%s: sleeping 5 sec...', data['status'])

        time.sleep(5)

        r = requests.get('https://api.routific.com/jobs/' + job_id)

        data = json.loads(r.text)

    logger.info('Got solution! Status code: %s', r.status_code)

    return data

#-------------------------------------------------------------------------------
def get_job_id(block, driver, start_address, depot_address):
    '''Use Routific long-running process endpoint to generate a job_id'''

    accounts = get_accounts(block)

    start = geocode(start_address)['geometry']['location']
    end = geocode(depot_address)['geometry']['location']

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
        "name": depot_address,
      },
      "shift_start": "8:00",
      "shift_end": "17:00"
    }

    for account in accounts['data']:
        address = account['address'] + ', ' + account['city'] + ', AB'

        result = geocode(address)

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
            "name": address,
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
            #"phone": account['phones'][0]['number'], # TODO: Test if exists
            "block": etap.get_udf('Block', account),
            "status": etap.get_udf('Status', account),
            "neighborhood": etap.get_udf('Neighborhood', account),
            "driver notes": etap.get_udf('Driver Notes', account),
            "office notes": etap.get_udf('Office Notes', account),
            "next pickup": etap.get_udf('Next Pickup Date', account)
          }
        }

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

        return job_id
    else:
        logger.error('Error retrieving Routific job_id. %s %s',
            r.headers, r.text)
        return False
