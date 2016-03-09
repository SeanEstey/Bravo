<h2>Mongo Collections</h2>

```json
"reminder_msgs": {
  "job_id": "[BSON ObjectId]",
  "name": "",
  "account_id": "",
  "call": {
    "sid": "twilio_call_id",
    "status": ["pending","active","failed","pending","queued","ringing","in-progress","busy","no-answer","completed"], 
    "answered_by": ["human", "machine"], 
    "ended_at": "[datetime]",
    "to": "phone_number",
    "speak": "",
    "attempts": "",
    "duration": "",
    "error_msg": "",
    "error_code": "",
  },
  "email": {
    "mid":  "mailgun_msg_id", 
    "status": ["pending", "bounced", "dropped", "delivered"],
    "recipient": "email",
    "error_msg": "",
    "error_code": ""
  },
  "custom": {
    "no_pickup": "[bool]",
    "next_pickup": "[datetime]",
    "other imported fields ..."
  }
}

"reminder_jobs": {
  "status": ["pending", "in-progress", "completed"], 
  "fire_dtime": "[datetime]", 
  "num_calls": "[Number]", 
  "template": {
    "call_template": "file.html",
    "email_template": "file.html",
    "email_subject": ""
  },
  "audio_url": "saved_audio_message_url"
}

"email_status": {
  "mid": "mailgun_msg_id",
  "status": ["queued", "delivered", "bounced", "dropped"],
  "data": {
    "reminder_msg_id": "mongo_id_for_updating_reminder",
    "sheet_name": "gsheets_name_for_updating_sheets",
}

"audio_msg": {
  "sid": "",
  "status": ""
}
```

<h2>Twilio</h2>

twilio.TwilioRestException
```json
{
  "status": "HTTP error code",
  "msg": "error message string",
  "code": "https://www.twilio.com/docs/api/errors/reference",
  "uri": "",
  "method": "POST/GET"
}
```

<a href="https://www.twilio.com/docs/api/rest/call#instance">Call Instance Resource</a>
<br>
Python: twilio.rest.resources.call
<br>
__dict__:
```json
{u'status': u'queued', u'answered_by': None, u'to_formatted': u'(780) 863-5715', 'parent': <twilio.rest.resources.calls.Calls object at 0x7efcbc3cefd0>, u'date_updated': None, u'price_unit': u'USD', u'phone_number_sid': u'PN3c6e7d07dd60172c7cbedcf1149c728d', u'parent_call_sid': None, 'auth': ('ACef54e4a38c29aa6a5ed6e5064e02e511', '47dbc1c341222df40eaaa941e48044bb'), 'notifications': <twilio.rest.resources.notifications.Notifications object at 0x7efcbc3dbdd0>, u'caller_name': None, u'from_formatted': u'(780) 413-8846', u'duration': None, u'group_sid': None, u'account_sid': u'ACef54e4a38c29aa6a5ed6e5064e02e511', u'annotation': None, 'feedback': <twilio.rest.resources.call_feedback.CallFeedbackFactory object at 0x7efcbc3dbfd0>, u'subresource_uris': {u'notifications': u'/2010-04-01/Accounts/ACef54e4a38c29aa6a5ed6e5064e02e511/Calls/CA7d1d19877dc768fd0c701cfcdc706fdd/Notifications.json', u'recordings': u'/2010-04-01/Accounts/ACef54e4a38c29aa6a5ed6e5064e02e511/Calls/CA7d1d19877dc768fd0c701cfcdc706fdd/Recordings.json'}, 'name': u'CA7d1d19877dc768fd0c701cfcdc706fdd', 'base_uri': 'https://api.twilio.com/2010-04-01/Accounts/ACef54e4a38c29aa6a5ed6e5064e02e511/Calls', u'start_time': None, u'direction': u'outbound-api', 'recordings': <twilio.rest.resources.recordings.Recordings object at 0x7efcbc3dbed0>, u'forwarded_from': None, u'to': u'+17808635715', u'end_time': None, 'timeout': <Unset Timeout Value>, u'sid': u'CA7d1d19877dc768fd0c701cfcdc706fdd', u'date_created': None, 'from_': u'+17804138846', u'price': None, u'api_version': u'2010-04-01'}
```
