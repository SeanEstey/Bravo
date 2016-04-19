import json
import requests
from geopy.geocoders import Nominatim
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

def get_accounts(block):
    # Get data from route via eTap API
    # stops = etap.call('
    accounts = etap.call('get_query_accounts', ETAP_WRAPPER_KEYS, {
      "query": block,
      "query_category": "ETW: Routes"
    })

    return accounts

def routific():
    job = json.loads(get_job_id('R1A', 'Steve', '', ''))

    r = requests.get('https://api.routific.com/jobs/' + job['job_id'])

    data = json.loads(r.text)

    while data['status'] != 'finished':
        print data['status'] + ': sleeping 5 sec...'

        time.sleep(5)

        r = requests.get('https://api.routific.com/jobs/' + job['job_id'])

        data = json.loads(r.text)


    print r.headers
    print r.status_code
    print r.text

    return True


def get_job_id(block, driver, start_address, depot_address):
    geolocator = Nominatim()

    accounts = get_accounts(block)

    office = geolocator.geocode('11131 131 St NW Edmonton AB')
    strathcona = geolocator.geocode('10347 73 Ave NW Edmonton AB')

    payload = {
      "visits": {},
      "fleet": {
        "Ryan": {
          "start_location": {
            "id": "Office",
            "lat": office.latitude,
            "lng": office.longitude,
            "name": "11130 131 St NW, T5M 1C3",
          },
          "end_location": {
            "id": "Strathcona",
            "lat": strathcona.latitude,
            "lng": strathcona.longitude,
            "name": "10347 73 Ave NW, T6E 1C1",
          },
          "shift_start": "8:00",
          "shift_end": "17:00"
        }
      }
    }

    for account in accounts['data']:
        addy = account['address'] + ' ' + account['city'] + ' AB'
        address = geolocator.geocode(addy)

        if not address:
            print "couldn't geolocate " + addy
            continue

        payload['visits'][account['name']] = {
          "location": {
            "name": account['address'] + ', ' + account['postalCode'],
            "lat": address.latitude,
            "lng": address.longitude
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
        return r.text
    else:
        print 'error!'
        print r.headers
        print r.text
        return False
