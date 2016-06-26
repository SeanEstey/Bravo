<h3>"users" collection</h3>
```json
{
  "user": "USERNAME",
  "password": "PASSWORD",
  "agency": "AGENCY_NAME"
}
```

<h3>"reminders" collection</h3>

```json
{
  "job_id": "<BSON.ObjectId>",
  "name": "",
  "account_id": "etapestry_account_id",
  "event_date": "<BSON.Date>",
  "voice": {
    "sid": "CA7d1d19877dc768fd0c701cfcdc706fdd [32 char Twilio ID]",
    "status": ["pending","active","failed","pending","queued",
               "ringing","in-progress","busy","no-answer","completed"], 
    "answered_by": ["human", "machine"], 
    "ended_at": "<BSON.Date>",
    "to": "PHONE_NUMBER",
    "speak": "[Text string spoken to user]",
    "attempts": "NUM_CALL_ATTEMPTS",
    "duration": "CALL_DURATION_IN_SECONDS",
    "error": "",
    "code": "",
  },
  "email": {
    "mid":  "mailgun_msg_id", 
    "status": ["pending", "bounced", "dropped", "delivered"],
    "recipient": "EMAIL_ADDRESS",
    "error": "",
    "code": ""
  },
  "custom": {
    "no_pickup": "[True,False]",
    "next_pickup": "<BSON.Date>",
    "status": "",
    "block": "",
    "type": ["pickup", "delivery", "dropoff"],
    "other imported fields": ""
  }
}
```

<h3>"jobs" collection</h3>

```json
{
  "agency": "AGENCY_NAME",
  "status": ["pending", "in-progress", "completed", "failed"], 
  "voice": {
    "fire_at": "<BSON.Date>",
    "started_at": "<BSON.Date>",
    "count": "[Number of calls]"
  },
  "email": {
    "fire_at": "<bson.date>",
    "started_at": "<bson.date>",
    "count": "[Number of emails]"
  },
  "schema": {
    "name": "",
    "voice_template": "file.html",
    "email_template": "file.html",
    "email_subject": "",
    "import_fields": {}
  },
  "audio_url": "saved_audio_message_url"
}
```

<h3>"emails" collection</h3>

```json
{
  "mid": "mailgun_msg_id",
  "status": ["queued", "delivered", "bounced", "dropped"],
  "code": "error code (if any)",
  "error": "(if any)",
  "reason": "error desc (if any)",
  "on_status_update": {
    "reminder_id": "<BSON.OjectId> (only for reminders)",
    "sheet": "sheet name (Google Sheets)",
    "worksheet": "worksheet name (Google Sheets)",
    "row": "row (Google Sheets)",
    "upload_status": "cell value (Google Sheets)"
  }
}
```

<h3>"agencies" collection</h3>

```json
{
  "name": "AGENCY_NAME",
  "etapestry": {
    "agency": "AGENCY_NAME",
    "user": "USERNAME",
    "pw": "PASSWORD",
    "endpoint": "https://sna.etapestry.com/v3messaging/service?WSDL",
    "query_category": "ETW: Routes",
    "gifts": {
      "fund": "WSF",
      "campaign": "Empties to WINN",
      "approach": "Bottle Donation"
    }
  },
  "twilio_auth_key": "PRIVATE_KEY",
  "gdrive": {
    "ss_ids": {
      "bravo": "1P51j2vTcaw0cNXGvvu_48J7yIztvS2-Yg4d1PwfWl3k",
      "stats": "1iBRJOkSH2LEJID0FEGcE3MHOoC5OKQsz0aH4AAPpTR4",
      "stats_archive": "1BTS-r3PZS3QVR4j5rfsm6Z4kBXoGQY8ur60uH-DKF3o",
      "inventory": "1Mb6qOvYVUF9mxyn3rRSoOik427VOrltGAy7LSIR9mnU",
      "route_template": "1Sr3aPhB277lESuOKgr2EJ_XHGPUhuhEEJOXfAoMnK5c",
    },
    "folder_ids": {
      "routed": "0BxWL2eIF0hwCRnV6YmtRLVBDc0E",
      "entered": "0BxWL2eIF0hwCOTNSSy1HcWRKUFk"
    },
  },
  "cal_ids": {
    "res": "7d4fdfke5mllck8pclcerbqk50@group.calendar.google.com",
    "bus": "bsmoacn3nsn8lio6vk892tioes@group.calendar.google.com"
  }
}
```

```json
"audio_msg": {
  "sid": "",
  "status": ""
}
```
