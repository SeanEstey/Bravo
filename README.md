<h2>Instructions</h2><br>

Install Dependencies<br>
```
apt-get install python-pip python-dev mongodb nginx rabbitmq-server
pip install celery flask flask-socketio flask-login pymongo python-dateutil twilio
```

Nginx/Php-fpm Setup<br>
```
apt-get install php-dev php-pear php5-curl
pecl install mongo
pear install Mail
pear install Net_SMTP
```

Clone repository<br>
```
git clone https://github.com/SeanEstey/Bravo
cd Bravo
```
Start RabbitMQ daemon<br>
`rabbitmqctl start_app`<br>
Start Flask Server:<br>
`python server.py`<br>

Create server_settings.py file with following variables set:<br>
```
DEBUG = [True/False]
DB_NAME = [MongoDB Db name]
ETW_RES_CALENDAR_ID = 
GOOGLE_SERVICE_ACCOUNT = [Google Service Email Address]
LOCAL_PORT = 
LOCAL_URL = [Localhost URL]
MAILGUN_API_KEY = 
MAILGUN_DOMAIN = 
PUB_URL = 
SECRET_KEY = ''
TITLE = 
TWILIO_ACCOUNT_SID = 
TWILIO_AUTH_ID = 

```

Setup Google API<br>
```
pip install apiclient oauth2client
pip install --upgrade google-api-python-client
```

Setup front end server to redirect to proper proxy addresses (see /config for Nginx .conf file)<br>

To manually shutdown server running in background<br>
get pid<br>
`ps aux | grep -m 1 'python server.py' | awk '{print $2}'`<br>
Kill it<br>
`kill -9 <PID>`<br>
(May need to run twice)
