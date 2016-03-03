<h2>Mongo Collections</h2>
<br>
```json
"reminder_msgs": {
  "job_id": "BSON ObjectId", 
  "call_status": "pending, active, failed, pending, queued, ringing, in-progress, busy, no-answer", 
  "email_status": "pending, bounced, dropped, delivered", 
  "attempts": "[Number]", 
  "answered_by": "human, machine", 
  "call_duration": "[twilio_number_seconds]", 
  "mid":  "[mailgun_email_id_string]", 
  "call_error": "", 
  "error_code": "", 
  "message": "[for announce template]", 
  "sid": "twilio_call_id_string", 
  "speak": "", 
  "code": "", 
  "ended_at": "[datetime]", 
  "rfu": "", 
  "no_pickup": "true, false", 
  "next_pickup": [datetime]
},
"reminder_jobs": {
  "status", "fire_dtime", "num_calls", "template", "audio_url", "message"
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
`python server.py`<br>

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


