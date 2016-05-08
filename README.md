<h2>Instructions</h2>
<br>

Install Dependencies
<br>
```
apt-get install python-pip python-dev mongodb nginx rabbitmq-server logrotate
pip install celery flask flask-socketio flask-login pymongo python-dateutil twilio apiclient oauth2client gspread
pip install --upgrade google-api-python-client
pip install oauth2client==1.5.2
```

Clone repository
<br>
```
git clone https://github.com/SeanEstey/Bravo
cd Bravo
```

<br>
Nginx/PHP Setup
<br>
-Copy PHP files to webroot (/var/www/bravo/php)
<br>
-Set proper webroot permissions for www-data user:
```
chown -R root:www-data /var/www/bravo/logs
chmod -R 660 /var/www/bravo/logs
```
-Create virtualhost file for nginx (/etc/nginx/sites-enabled/default)
<br>

Logrotate Setup
<br>
-Copy logrotate/bravo to /etc/logrotate.d/
<br>

Setup Mongo Logins
<br>
```
$mongo
>> use wsf
>> db.logins.insert({'user':'name', 'pass':'password'})
```

Get Google Service Account Credentials
<br>
-Open Google Developer Console
<br>
-Find Service Account
<br>
-Generate JSON key
<br>
-Save to flask dir as "oauth_credentials.json"
<br>

Start RabbitMQ daemon<br>
`rabbitmqctl start_app`<br>
Start Flask Server:<br>
`python main.py`<br>

Create private_config.py file with following variables set:
<br>
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

Setup front end server to redirect to proper proxy addresses (see /config for Nginx .conf file)<br>

To manually shutdown server running in background<br>
get pid<br>
`ps aux | grep -m 1 'python main.py' | awk '{print $2}'`<br>
Kill it<br>
`kill -9 <PID>`<br>
(May need to run twice)

<br>
Start Server
```
python main.py
```
