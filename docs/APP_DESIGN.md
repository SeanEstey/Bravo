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
    "trig_ids": [ 
        "ObjectId(...)" 
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
  "evnt_id": "ObjectId(...)",
  "status": "pending",
  "fire_dt": "new Date(2016-10-07T08:00:00-0600)",
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
  "type": "voice",
  "trig_id": "bson.object",
  "acct_id": "ObjectId(...)",
  "to": "(780) 863-5715",
  "evnt_id": "ObjectId(...)",
  "event_dt": "new Date(2016-10-09T08:00:00-0600)",
  "content": {
    "source": "template",
    "template": {
      "default": {
        "file": "voice/vec/reminder.html"
      }
    }
  },
  "tracking": {
    "sid": "CA78b7529052a8c7bd161728fecd2480d4",
    "attempts": 1,
    "answered_by": "human",
    "duration": "28",
    "ended_at": "new Date(1475507397211)",
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
