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

"emails": {
  "mid": "mailgun_msg_id",
  "status": ["queued", "delivered", "bounced", "dropped"],
  "code": "error code (if any)",
  "error": "(if any)",
  "reason": "error desc (if any),
  "optional": {
    "reminder_msg_id": "mongo_id_for_updating_reminder",
    "sheet_name": "gsheets_name_for_updating_sheets"
  }
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
dict dump:
```json
{
  "sid": "CA7d1d19877dc768fd0c701cfcdc706fdd", 
  "status": "queued", 
  "answered_by": "None", 
  "to_formatted": "(780) 863-5715", 
  "parent": "<twilio.rest.resources.calls.Calls object at 0x7efcbc3cefd0>", 
  "date_updated": "None", 
  "price_unit": "USD", 
  "phone_number_sid": "PN3c6e7d07dd60172c7cbedcf1149c728d", 
  "parent_call_sid": "None", 
  "auth": "(ACef54e4a38c29aa6a5ed6e5064e02e511, {{ secret_key }})", 
  "notifications": "<twilio.rest.resources.notifications.Notifications object at 0x7efcbc3dbdd0>", 
  "caller_name": "None", 
  "from_formatted": "(780) 413-8846", 
  "duration": "None", 
  "group_sid": "None", 
  "account_sid": "ACef54e4a38c29aa6a5ed6e5064e02e511", 
  "annotation": "None", 
  "feedback": "<twilio.rest.resources.call_feedback.CallFeedbackFactory object at 0x7efcbc3dbfd0>", 
  "subresource_uris": "{}", 
  "name": "CA7d1d19877dc768fd0c701cfcdc706fdd", 
  "base_uri": "https://api.twilio.com/2010-04-01/Accounts/ACef54e4a38c29aa6a5ed6e5064e02e511/Calls", 
  "start_time": "None", 
  "direction": "",
  "outbound-api": "", 
  "recordings": "<twilio.rest.resources.recordings.Recordings object at 0x7efcbc3dbed0>", 
  "forwarded_from": "None", 
  "to": "+17808635715", 
  "end_time": "None", 
  "timeout": "<Unset Timeout Value>", 
  "date_created": "None", 
  "from_": "+17804138846", 
  "price": "None", 
  "api_version": "2010-04-01"}
```
