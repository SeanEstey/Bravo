import json
import requests
import time

from config import *
import etap

log_handler = logging.FileHandler('routing.log')
log_formatter = logging.Formatter('[%(asctime)s %(name)s] %(message)s','%m-%d %H:%M')
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)

#-------------------------------------------------------------------------------
def geocode(address):
    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {
      'address': address,
      'key': GOOGLE_API_KEY
    }

    try:
        r = requests.get(url, params=params)
    except Exception as e:
        print 'geocoding error'
        print e
        return False

    response = json.loads(r.text)

    if len(response['results']) > 1:
        print "Multiple results geocoded for " + address
        print 'Returning first result (usually more accurate)'

    if response['status'] == 'ZERO_RESULTS':
        print "No geocode result for " + address
        return False
    elif response['status'] == 'INVALID_REQUEST':
        print "Improper address " + address
        return False
    elif response['status'] != 'OK':
        print "Error geocoding " + address
        print response
        return False

    return response['results'][0]['geometry']['location']

#-------------------------------------------------------------------------------
def get_accounts(block):
    # Get data from route via eTap API
    # stops = etap.call('
    accounts = etap.call('get_query_accounts', ETAP_WRAPPER_KEYS, {
      "query": block,
      "query_category": "ETW: Routes"
    })

    return accounts


def routific():
    job_id = get_job_id('R1A', 'Steve', '', '')
    solution = get_solution(job_id)
    print solution
    return True

#-------------------------------------------------------------------------------
def get_solution(job_id):
    r = requests.get('https://api.routific.com/jobs/' + job_id)

    data = json.loads(r.text)

    while data['status'] != 'finished':
        print data['status'] + ': sleeping 5 sec...'

        time.sleep(5)

        r = requests.get('https://api.routific.com/jobs/' + job_id)

        data = json.loads(r.text)


    print r.headers
    print r.status_code
    print r.text

    return True

#-------------------------------------------------------------------------------
def get_job_id(block, driver, start_address, depot_address):
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
            print "couldn't geolocate " + addy
            continue

        payload['visits'][account['name']] = {
          "location": {
            "name": account['address'] + ', ' + account['postalCode'],
            "lat": coords['lat'],
            "lng": coords['lng']
          },
          "start": "8:00",
          "end": "17:00",
          "duration": 3,
          "customNotes": {
            "id": account['id'],
            "block": etap.get_udf('Block', account),
            "status": etap.get_udf('Status', account),
            "neighborhood": etap.get_udf('Neighborhood', account),
            "driver notes": etap.get_udf('Driver Notes', account),
            "office notes": etap.get_udf('Office Notes', account)
          }
        }

    url = 'https://api.routific.com/v1/vrp-long'
    headers = {
        'content-type': 'application/json',
        'Authorization': ROUTIFIC_KEY
    }

    try:
        r = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload)
        )
    except Exception as e:
        print e
        #logger.error(e)
        return False

    if r.status_code == 202:
        return json.loads(r.text)['job_id']
    else:
        print 'error!'
        print r.headers
        print r.text
        return False
