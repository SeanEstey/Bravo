'''app.routing.routific'''
import json, requests
from flask import g
from app.lib.loggy import Loggy
from app.main.etap import get_udf, get_prim_phone
log = Loggy('routific')

#-------------------------------------------------------------------------------
def submit_vrp_task(orders, driver, start, end, shift_start, shift_end, api_key):

    agcy = g.db.agencies.find_one({'routing.routific.api_key':api_key})['name']
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
        # 'traffic': ['faster' (default), 'fast', 'normal', 'slow', 'very slow']
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
        log.error('Routific exception=%s', str(e), group=agcy)
        log.exception(str(e), group=agcy)
        return False

    if r.status_code != 202:
        log.error('Failed to retrieve Routific job_id. Msg="%s"',
            r.text['error'], group=agcy)
        return False

    return json.loads(r.text)['job_id']

#-------------------------------------------------------------------------------
def order(acct, formatted_address, geo, shift_start, shift_end, min_per_stop):
    return {
      "location": {
        "name": formatted_address,
        "lat": geo['geometry']['location']['lat'],
        "lng": geo['geometry']['location']['lng']
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
