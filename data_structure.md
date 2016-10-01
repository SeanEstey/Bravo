<h3>Reminder Jobs</h3>
-Each document represents a group of reminders for a specific event date
-Reminder documents contain the "_id" of the parent job as "job_id"
-Jobs manage fire triggers and overall status for each type of notification ['voice', 'sms', 'email']

<h4>JSON Structure</h4>

```json
{
    "agency": "name",
    "status": ["pending", "in-progress", "completed", "failed"], 
    "name": "name",
    "event_dt": "datetime of event",
    "no_pickups": "num opt-outs",
    "voice": {
	"status": ["pending", "in-progress", "completed", "failed"],
        "fire_dt": "bson.date in UTC",
        "started_dt": "bson.date in UTC",
        "count": "number"
    },
    "email": {
	"status": ["pending", "in-progress", "completed", "failed"],
        "fire_dt": "<bson.date>",
        "started_dt": "<bson.date>",
        "count": "number"
    },
    "sms": {
	"status": ["pending", "in-progress", "completed", "failed"],
	"fire_dt": "bson.date",
	"count": "number"
    },
    "schema": {
        "_comment": "fields imported from templates/schemas/[name].json",
        "name": "pickup_reminder",
        "type": "reminder",
        "description": "display when adding job",
        "email": {
            "_comments": "any emails sent as followups to scheduled reminder", 
            "no_pickup": {
                "file": "email/vec/no_pickup.html",
                "subject": "string"
            }
        }
    }
}
```

<h3> Reminders </h3>
-Each document represents one or more notifications to a recipient for a specific event date
-A reminder can have 1 notification for each medium ['voice', 'sms', 'email'], each with its own trigger time set by its parent job
-If a reminder is set for Email and SMS, it contains 'email' and 'sms' keys, but not 'voice' key

<h4>JSON Structure</h4>

```json
{
    "job_id": "<BSON.ObjectId>",
    "agency": "agency name",
    "name": "customer name",
    "account_id": "etapestry account number",
    "event_dt": "<BSON.Date>",
    "voice": {
        "conf": {
            "_comment": "call settings",
            "to": "phone number string",
            "fire_dt": "datetime to send",
            "source": ["template", "audio_url"],
            "template": ".html path if source=='template'",
            "audio_url": "url of recorded audio if source=='audio_url'"
        },
        "call": {
            "_comment": "data/status from the outbound call",
            "sid": "32 char twilio call id",
            "status": [
                "no-number", "pending","active","cancelled", "failed","queued",
                "ringing","in-progress","busy","no-answer","completed"
            ], 
            "answered_by": ["human", "machine"],
            "ended_dt": "bson.date in UTC",
            "speak": "text spoken to user",
            "attempts": "number",
            "duration": "number in sec",
            "error": "twiilo msg",
            "code": "twilio code"
        }
    },
    "email": {
        "conf": {
            "recipient": "email address",
            "fire_dt": "bson.date in UTC",
            "template": ".html path of content",
            "subject": "subject line"
        },
        "mailgun": {
            "mid":  "mailgun id",
            "fire_dt": "bson.date in UTC",
            "status": ["no-email", "pending", "bounced", "dropped", "delivered"],
            "error": "mailgun error (if any)",
            "code": "mailgun status code"
        }
    },
    "custom": {
        "_comment": "any fields that are specific to the reminder type",
        "no_pickup": "[True,False]",
        "future_pickup_dt": "<BSON.Date>",
        "status": "",
        "block": "",
        "type": ["pickup", "delivery", "dropoff"]
    }
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

<h3>Agencies JSON Structure</h3>

```json
{
    "name": "3 char abbrev",
    "etapestry": {
        "agency": "3 char abbrev",
        "user": "login",
        "pw": "password",
        "endpoint": "https://sna.etapestry.com/v3messaging/service?WSDL",
        "query_category": "ETW: Routes",
        "gifts": {
            "fund": "WSF",
            "campaign": "Empties to WINN",
            "approach": "Bottle Donation"
        }
    },
    "google": {
        "cal": {
            "res": "7d4fdfke5mllck8pclcerbqk50@group.calendar.google.com",
            "bus": "bsmoacn3nsn8lio6vk892tioes@group.calendar.google.com"
        },
        "oauth": {
            "type": "service_account",
            "project_id": "project-id-uicnlcvxxveqfuokxwj",
            "private_key_id": "8a11b7ea91f73f3490b347848e69e6c5d1174804",
            "private_key": "-----BEGIN PRIVATE KEY-----KEY_DATA-----END PRIVATE KEY-----",
            "client_email": "bravo-738@project-id-uicnlcvxxveqfuokxwj.iam.gserviceaccount.com",
            "client_id": "100311906177554855345",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://accounts.google.com/o/oauth2/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "long url"
        },
        "geocode": {
            "api_key": "40 char key from service account"
        }
    },
    "reminders": {
        "days_in_advance_to_schedule": 2,
        "email": {
          "fire_days_delta": -2,
          "fire_hour": 8,
          "fire_min": 0
        },
        "phone": {
          "redial_delay": 300,
          "max_call_attempts": 2,
          "fire_days_delta": -1,
          "fire_hour": 19,
          "fire_min": 0
        }
    },
    "routing": {
        "office": {
          "name": "Vecova",
          "formatted_address": "3304 33 St NW, Calgary, AB",
          "url": "google maps url"
        },
        "depots": [
          {
            "name": "Vecova",
            "formatted_address": "3304 33 St NW, Calgary, AB"
          }
        ],
        "drivers": [
          {
            "name": "Steve",
            "shift_start": "09:00"
          }
        ],
        "gdrive": {
          "template_sheet_id": "1Sr3aPhB277lESuOKgr2EJ_XHGPUhuhEEJOXfAoMnK5c",
          "routed_folder_id": "0B2PiOyJMXwxZU0VlNjVDTmlXYUE",
          "permissions": [
            {
              "email": "sean.vecova@gmail.com",
              "role": "owner"
            }
          ]
        },
        "routific": {
            "_comments": "auth/settings for routing engine",
            "api_key": "long str key"
            "traffic": "normal",
            "min_per_stop": 4,
            "office_address": "3304 33 St NW, Calgary, AB",
            "shift_end": "18:00"
        },
        "view_days_in_advance": 4
    },
    "twilio": {
        "caller_id": "Vecova",
        "ph": "outgoing number, international format (+14031234567)",
        "sms": "outgoing text number, international format (+14031234567)",
        "keys": {
            "main": {
                "app_sid": "id of app for calls to/from twilio client",
                "sid": "34 char account id",
                "auth_id": "32 auth id"
            },
            "test": {
                "sid": "34 char account id",
                "auth_id": "32 char auth id"
            }
        }
    }
}
```

<h3>Users JSON Structure</h3>
```json
{
  "user": "USERNAME",
  "password": "PASSWORD",
  "agency": "AGENCY_NAME",
  "admin": "True/False"
}
```

<h3>Audio_msg JSON Structure</h3>
```json
"audio_msg": {
  "sid": "",
  "status": ""
}
```