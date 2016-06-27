### Python/PHP Setup Instructions

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
Copy bravo/php files to webroot /var/www/bravo/php

Create log folder:

`$mkdir /var/www/bravo/logs`

Create blank log files in this folder: debug.log, info.log, error.log, tests.log

Set proper webroot permissions for www-data user:
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
1. For each agency, open Google Developer Console
2. Find Service Account
3. Generate JSON key
4. Add contents to MongoDB "agencies" collection under "oauth" key

###### Create auth_keys.py in flask/ with following variables:
```
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
ROUTIFIC_KEY = ''
```

### Google Sheets / Google Script Setup Instructions

From Google Drive, create new Sheet named `Bravo Sheets` with worksheets `Routes`, `RFU`, `MPU`, `Signups`

From Google Drive, create new Script. Open it. Tools->Script Editor, copy the ID in URL.

Install node.js and npm:

`apt-get install npm nodejs`

Install node-google-apps-script (https://github.com/danthareja/node-google-apps-script)

`npm install -g node-google-apps-script`

Go to Google Developer Console, create new project, create Google ClientID Oauth key, download JSON file.

Place in Bravo/gscript.

Setup gapps:

`gapps auth -b /path/to/key.json`

Init gapps:

```
$cd Bravo/gscript
$gapps init <gdrive_script_id>
```

Make sure the .gs files are in Bravo/gscript/src.

<b>[I had some kind of permissions issue, can't recall how I sorted it out. Think I had to change the gapps executable permissions or change the npm install directory...]</b>

### Google Sheets User Permissions

Share the Bravo Library script with new user with View permissions.

Have the user open the Library in Script Editor, run a test function. 

Authorize permissions.

Share Bravo Sheets with new user with Edit permissions.

Have user open Bravo Sheets Script Editor, Resources->Libraries, paste in Bravo Library Project Key

Have user remove Bravo Library script from Google Drive.

Make sure user has all required Calendar's, Sheets, Gdrive Folders shared with them.

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
