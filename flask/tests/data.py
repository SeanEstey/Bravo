import json
from dateutil.parser import parse

with open('templates/reminder_schemas.json') as json_file:
  schemas = json.load(json_file)

job = {
  'schema': schemas['etw'],
  'status': 'pending',
  'name': 'job_a',
  'voice': {
      'fire_at': parse('Dec 31, 2015'),
      'count': 1
  },
}

reminder = {
    'name': 'Test Res',
    'account_id': '57515',
    'event_date': parse('December 31, 2014'),
    'voice': {
      'sid': 'ABC123ABC123ABC123ABC123ABC123AB',
      'status': 'pending',
      'attempts': 0,
      'to': '780-863-5715',
    },
    'email': {
      'status':  'pending',
      'recipient': 'estese@gmail.com'
    },
    'custom': {
      'next_pickup': parse('June 21, 2016'),
      'type': 'pickup',
      'status': 'Active',
      'office_notes': '',
      'cancel_pickup_url':  '',
      'account': {}
    }
}

email = {
    'mid': 'abc123',
    'status': 'queued',
    'on_status_update': {
      'worksheet': 'Routes',
      'row': 2,
      'upload_status': 'Success'
    }
}

gift = {
    "account_number": 57515, # Test Res
    "date": "04/06/2016",
    "amount": 10.00,
    "status": "Active",
    "next_pickup": "21/06/2016",
    "from": {
        "sheet": "Routes",
        "row": 3,
        "upload_status": "Success"
    }
}

zero_gift = {
    "account_number": 57515, # Test Res
    "date": "04/06/2016",
    "amount": 0.00,
    "status": "Active",
    "next_pickup": "21/06/2016",
    "from": {
        "sheet": "Routes",
        "row": 2,
        "upload_status": "Success"
    }
}

gift_cancelled_act = {
    "account_number": 71675, # Cancelled Status
    "date": "04/06/2016",
    "amount": 0.00,
    "status": "Cancelled",
    "next_pickup": "21/06/2016",
    "from": {
        "sheet": "Routes",
        "row": 4,
        "upload_status": "Success"
    }
}

