### Setup Instructions

###### Install Dependencies
```
apt-get install \
    python-pip python-dev \
    mongodb \
    nginx \
    rabbitmq-server \
    logrotate
pip install \
    celery \
    pymongo \
    python-dateutil \
    twilio \
    apiclient oauth2client gspread \
    flask flask-socketio flask-login 
pip install --upgrade google-api-python-client
pip install oauth2client==1.5.2
```

###### Clone repository
```
git clone https://github.com/SeanEstey/Bravo
cd Bravo
```

###### PHP Setup
-Copy bravo/php files to webroot /var/www/bravo/php

-Create log folder:

'$mkdir /var/www/bravo/logs'
-Create blank log files in this folder: debug.log, info.log, error.log, tests.log
-Set proper webroot permissions for www-data user:
```
chown -R root:www-data /var/www/bravo
chmod -R 660 /var/www/bravo
```

###### Setup Nginx Virtual Host
Copy bravo/virtual_host/default to /etc/nginx/sites-enabled

###### Logrotate Setup
Copy logrotate/bravo to /etc/logrotate.d/

###### Setup Mongo Logins
```
$mongo
>> use wsf
>> db.logins.insert({'user':'name', 'pass':'password'})
```

###### Get Google Service Account Credentials
1. Open Google Developer Console
2. Find Service Account
3. Generate JSON key
4. Save to Bravo/flask as `oauth_credentials.json`

###### Create auth_keys.py in flask/ with following variables:
```
ETW_RES_CALENDAR_ID = 
GOOGLE_SERVICE_ACCOUNT = [Google Service Email Address]
GOOGLE_API_KEY = ''
MAILGUN_API_KEY = ''
MAILGUN_DOMAIN = ''
SECRET_KEY = ''
BRAVO_AUTH_KEY = ''
TWILIO_ACCOUNT_SID = ''
TWILIO_AUTH_ID = ''
TWILIO_TEST_ACCOUNT_SID = ''
TWILIO_TEST_AUTH_ID = ''
SECRET_KEY = ''
LOGIN_USER = ''
LOGIN_PW = ''
ROUTIFIC_KEY = ''
ETAP_WRAPPER_KEYS = {
  'association_name': '',
  'etap_endpoint': '',
  'etap_user': '',
  'etap_pass': ''
}
```

### Run Instructions

###### Start RabbitMQ daemon
`$rabbitmqctl start_app`

###### Start Flask Server
`$python main.py`

This will start the celery workers.

### Shutdown Instructions

If running in foreground, kill with CTRL+C. This will kill Celery workers.

If running in background, get pid:

`$ps aux | grep -m 1 'python main.py' | awk '{print $2}'`

Now kill it using that PID:

`$kill -9 <PID>`

(May need to run twice)
