'''app.routing.routific'''
import json, requests
from flask import g
from app.main.etapestry import get_udf as udf, get_prim_phone as prim_phone
from logging import getLogger
log = getLogger(__name__)

'''Methods called from .build module. g.group set'''

#-------------------------------------------------------------------------------
def submit_vrp_task(orders, driver, start_addr, end_addr, shift_start, shift_end, api_key):
    """@start_addr, end_addr: formatted address str's returned from Google
    geocoder.
    """

    payload = {
        "visits": { order["customNotes"]["id"]:order for order in orders },
        "fleet": {
            driver: {
                "start_location": {
                    "id": "office",
                    "name": start_addr,
                    "address": start_addr
                },
                "end_location": {
                    "id": "depot",
                    "name":end_addr,
                    "address": end_addr
                },
                "shift_start": shift_start
            }
        },
        "options": {
            "traffic": "slow",
            "shortest_distance": True,
            # TODO: testing Here geocoder
            "geocoder": "here"
        }
    }

    try:
        r = requests.post('https://api.routific.com/v1/vrp-long',
            headers = {'content-type':'application/json', 'Authorization':api_key},
            data=json.dumps(payload))
    except Exception as e:
        log.exception('Routific error submitting vrp_task: %s', str(e))
        return False

    if r.status_code != 202:
        log.error('Failed to retrieve Routific job_id. Msg="%s"', r.text)
        return False

    return json.loads(r.text)['job_id']

#-------------------------------------------------------------------------------
def here_order(acct, geolocation, start, end, duration):
    """@addr: google geocoder formatted address str
    """
    return {
      "gmaps_url": "",
      "location": {
        "name":geolocation["formatted_address"],
        "address": geolocation["formatted_address"]
      },
      "start": start,
      "duration": int(duration),
      "customNotes": {
        "id": acct['id'],
        "lat": geolocation.get('geometry',{}).get('location',{}).get('lat',{}),
        "lng": geolocation.get('geometry',{}).get('location',{}).get('lng',{}),
        "name": acct['name'],
        "phone": prim_phone(acct),
        "email": 'Yes' if acct.get('email') else 'No',
        "contact": udf('Contact', acct),
        "block": udf('Block', acct),
        "status": udf('Status', acct),
        "neighborhood": udf('Neighborhood', acct),
        "driver notes": udf('Driver Notes', acct),
        "office notes": udf('Office Notes', acct),
        "next pickup": udf('Next Pickup Date', acct)
      }
    }

#-------------------------------------------------------------------------------
def order(acct, loc_name, geo, shift_start, shift_end, min_per_stop):
    return {
      "gmaps_url": "",
      "location": {
        "address": loc_name,
        "name": loc_name, #,
        "lat": geo.get('geometry',{}).get('location',{}).get('lat',{}),
        "lng": geo.get('geometry',{}).get('location',{}).get('lng',{})
      },
      "start": shift_start,
      "duration": int(min_per_stop),
      "customNotes": {
        "lat": geo.get('geometry',{}).get('location',{}).get('lat',{}),
        "lng": geo.get('geometry',{}).get('location',{}).get('lng',{}),
        "id": acct['id'],
        "name": acct['name'],
        "phone": prim_phone(acct),
        "email": 'Yes' if acct.get('email') else 'No',
        "contact": udf('Contact', acct),
        "block": udf('Block', acct),
        "status": udf('Status', acct),
        "neighborhood": udf('Neighborhood', acct),
        "driver notes": udf('Driver Notes', acct),
        "office notes": udf('Office Notes', acct),
        "next pickup": udf('Next Pickup Date', acct)
      }
    }
