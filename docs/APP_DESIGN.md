<h3>Notification Events</h3>
-Each document represents a set of triggers and corresponding notifications for an event
<br>
-An event can contain 1 or more triggers for <b>voice</b> or <b>email</b> notifications
<br>
-Status status starts as <b>pending</b>, once one of its triggers is fired,
changes to <b>in-progress</b>, and changes to <b>complete</b> when all triggers are fired

<h4>JSON Structure</h4>

```json
{
    "agency": "name",
    "status": ["pending", "in-progress", "completed", "failed"], 
    "name": "name",
    "event_dt": "datetime of event",
    "triggers": [
        {"id": "bson.objectid"},
        {"id": "bson.objectid"}
    ]
}
```

<h3>Triggers</h3>
-Represent 1 or more notifications
<br>
-Monitored by cron process. When a triggers "fire_dt" datetime is reached, it is triggered, and all it's dependent notifications are sent
<br>

<h4>JSON Structure</h4>
```json
{
  "event_id": ObjectId("57f2ae87fd9ab4312024a8c7"),
  "status": "pending",
  "fire_dt": new Date("2016-10-07T08:00:00-0600"),
  "type": "email"
}
```

<h3>Notifications</h3>
-The actual <b>email</b>, <b>voice</b>, or <b>sms</b> notification to send
<br>
-Contains recipient account properties, 

<h4>JSON Structure</h4>

```json
{
  "status": "completed",
  "trig_id": "bson.object",
  "account": {
    "udf": {
    },
    "name": "Sean Estey",
    "id": 5075
  },
  "to": "(780) 863-5715",
  "event_id": ObjectId("57f2ae87fd9ab4312024a8c7"),
  "content": {
    "source": "template",
    "template": {
      "default": {
        "file": "voice/vec/reminder.html"
      }
    }
  },
  "type": "voice",
  "event_dt": new Date("2016-10-09T08:00:00-0600"),
  "sid": "CA78b7529052a8c7bd161728fecd2480d4",
  "attempts": 1,
  "answered_by": "human",
  "duration": "28",
  "ended_at": new Date(1475507397211),
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

<h3>Users</h3>

<h4>Users JSON Structure</h4>

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

<h3>Emails</h3>

<h4>JSON Structure</h4>

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
