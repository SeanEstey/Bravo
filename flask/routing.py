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

    for stop in solution['output']['solution'][form['driver']]:
        id = stop['location_id']

        if id in solution['input']['visits']:
            stop['customNotes'] = solution['input']['visits'][id]['customNotes']

            stop['gmaps_url'] = get_gmaps_url(
                stop['location_name'],
                stop['customNotes']['lat'],
                stop['customNotes']['lng']
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

    # TODO: Test for partial results status

    if len(response['results']) > 1:
        logger.info("Multiple results geocoded for %s. Returning first result.", address)

    if response['status'] == 'ZERO_RESULTS':
        logger.info("No geocode result for %s", address)
        return False
    elif response['status'] == 'INVALID_REQUEST':
        logger.info("Improper address %s", address)
        return False
    elif response['status'] != 'OK':
        logger.info("Error geocoding %s. %s", address, response)
        return False

    return response['results'][0]['geometry']['location']

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

    logger.info('Got solution! %s %s', r.headers, r.status_code)

    return data

#-------------------------------------------------------------------------------
def get_job_id(block, driver, start_address, depot_address):
    '''Use Routific long-running process endpoint to generate a job_id'''

    accounts = get_accounts(block)

    office = geocode('11131 131 St NW, Edmonton AB, T5M 1C1')
    strathcona = geocode('10347 73 Ave NW Edmonton AB')

    payload = {
      "visits": {},
      "fleet": {
        "Ryan": {
          "start_location": {
            "id": "Office",
            "lat": office['lat'],
            "lng": office['lng'],
            "name": "11130 131 St NW, T5M 1C3",
          },
          "end_location": {
            "id": "Strathcona",
            "lat": strathcona['lat'],
            "lng": strathcona['lng'],
            "name": "10347 73 Ave NW, T6E 1C1",
          },
          "shift_start": "8:00",
          "shift_end": "17:00"
         }
      }
    }

    for account in accounts['data']:
        addy = account['address'] + ' ' + account['city'] + ' AB, ' + account['postalCode']

        coords = geocode(addy)

        if not coords:
            logger.info("Couldn't geolocate %s", addy)
            continue

        payload['visits'][account['id']] = { # location_id
          "location": {
            "name": account['address'] + ', ' + account['postalCode'],
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
            "office notes": etap.get_udf('Office Notes', account)
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
