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
