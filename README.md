<h2>Mongo Collections</h2>

```json
"reminder_msgs": {
  "job_id": "[BSON ObjectId]",
  "name": "",
  "account_id": "",
  "call": {
    "sid": "twilio_call_id",
    "status": ["pending","active","failed","pending","queued","ringing","in-progress","busy","no-answer"], 
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
```

<h2>Instructions</h2>
<br>

Install Dependencies
<br>
```
apt-get install python-pip python-dev mongodb nginx rabbitmq-server
pip install celery flask flask-socketio flask-login pymongo python-dateutil twilio apiclient oauth2client gspread
pip install --upgrade google-api-python-client
```

Clone repository
<br>
```
git clone https://github.com/SeanEstey/Bravo
cd Bravo
```
Start RabbitMQ daemon<br>
`rabbitmqctl start_app`<br>
Start Flask Server:<br>
`python main.py`<br>

Create private_config.py file with following variables set:
<br>
```
ETW_RES_CALENDAR_ID = 
GOOGLE_SERVICE_ACCOUNT = [Google Service Email Address]
MAILGUN_API_KEY = 
MAILGUN_DOMAIN = 
SECRET_KEY = ''
TWILIO_ACCOUNT_SID = 
TWILIO_AUTH_ID = 
```

Setup front end server to redirect to proper proxy addresses (see /config for Nginx .conf file)<br>

To manually shutdown server running in background<br>
get pid<br>
`ps aux | grep -m 1 'python server.py' | awk '{print $2}'`<br>
Kill it<br>
`kill -9 <PID>`<br>
(May need to run twice)


