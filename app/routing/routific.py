'''app.routing.routific'''
import json, requests
from flask import g
from app.main.etap import get_udf, get_prim_phone
from logging import getLogger
log = getLogger(__name__)

'''Methods called from .build module. g.group set'''

#-------------------------------------------------------------------------------
def submit_vrp_task(orders, driver, start, end, shift_start, shift_end, api_key):

    start_loc = start['geometry']['location']
    end_loc = end['geometry']['location']

    payload = {
      "visits": {},
      "fleet": {
        driver: {
          "start_location": {
            "id": "office",
            "lat": start_loc['lat'],
            "lng": start_loc['lng'],
            "name": start['formatted_address']
           },
          "end_location": {
            "id": "depot",
            "lat": end_loc['lat'],
            "lng": end_loc['lng'],
            "name": end['formatted_address']
          },
          "shift_start": shift_start,
          "shift_end": shift_end
        }
      },
      "options": {
        "traffic": "slow",
        "shortest_distance": True
      }
    }

    for order in orders:
        payload['visits'][order['customNotes']['id']] = order

    try:
        r = requests.post(
            'https://api.routific.com/v1/vrp-long',
            headers = {
              'content-type': 'application/json',
              'Authorization': api_key
            },
            data=json.dumps(payload)
        )
    except Exception as e:
        log.error('Routific exception=%s', str(e))
        log.exception(str(e))
        return False

    if r.status_code != 202:
        log.error('Failed to retrieve Routific job_id. Msg="%s"', r.text)
        return False

    return json.loads(r.text)['job_id']

#-------------------------------------------------------------------------------
def order(acct, loc_name, geo, shift_start, shift_end, min_per_stop):
    return {
      "gmaps_url": "",
      "location": {
        "name": loc_name,
        "lat": geo.get('geometry',{}).get('location',{}).get('lat',{}),
        "lng": geo.get('geometry',{}).get('location',{}).get('lng',{})
      },
      "start": shift_start,
      "end": shift_end,
      "duration": int(min_per_stop),
      "customNotes": {
        "id": acct['id'],
        "name": acct['name'],
        "phone": get_prim_phone(acct),
        "email": 'Yes' if acct.get('email') else 'No',
        "contact": get_udf('Contact', acct),
        "block": get_udf('Block', acct),
        "status": get_udf('Status', acct),
        "neighborhood": get_udf('Neighborhood', acct),
        "driver notes": get_udf('Driver Notes', acct),
        "office notes": get_udf('Office Notes', acct),
        "next pickup": get_udf('Next Pickup Date', acct)
      }
    }
