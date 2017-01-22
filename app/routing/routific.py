'''app.routing.routific'''
import json
import logging
import requests
from .. import etap
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def submit_vrp_task(orders, driver, start, end, shift_start, shift_end, api_key):
    payload = {
      "visits": {},
      "fleet": {
        driver: {
          "start_location": {
            "id": "office",
            "lat": start['geometry']['location']['lat'],
            "lng": start['geometry']['location']['lng'],
            "name": start['formatted_address']
           },
          "end_location": {
            "id": "depot",
            "lat": end['geometry']['location']['lat'],
            "lng": end['geometry']['location']['lng'],
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
        log.error('Routific exception=%s', str(e))
        log.debug(str(e), exc_info=True)
        return False

    if r.status_code != 202:
        log.error('Failed to retrieve Routific job_id. Msg="%s"',r.text['error'])
        return False

    return json.loads(r.text)['job_id']

#-------------------------------------------------------------------------------
def order(account, formatted_address, geo, shift_start, shift_end, min_per_stop):
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
