### Setup Instructions

###### Clone repository
```
git clone https://github.com/SeanEstey/Bravo --branch <b_name>
cd Bravo
```

###### Install Ubuntu Packages

Follow instructions in requirements/pkg_list.txt

###### Install Python Packages

Follow instructions in requirements/requirements.txt

###### Run setup

`python setup.py`

This will copy nginx virtual host file and setup logrotate.d

Add execution permission to /var/www/bravo/logs folder. 

Create empty files: info.log, debug.log, error.log. Add execution permissions.

###### PHP Error Logging

Open /etc/php.ini

Find error_log line. Set:
`error_log = /root/bravo/logs/debug.log`

###### Create MongoDB Auth File

Create "db_auth.py" in Bravo root directory:
```
user = "db_user"
password = "db_pw"
```

##### Domain & Webhooks

######Live Server

Update DNS records to point to IP address of VPS.
The Mailgun and Twilio webhooks use the domain name so they will point resolve to the new IP address once the DNS changes sync.

######Test Server

Mailgun webhooks 

-Update webhooks for sandbox domain: https://mailgun.com/app/webhooks

Twilio webhooks

-Update webhooks for Alice test Number:
-Go to appropriate subaccount
-Phone Numbers->Alice (Test Server)->Messaging
-Update "A Message Comes In" webhook with VPS IP address

#####Setup MongoDB

Create database named "bravo"

Create collections: "users", "agencies", "maps"

Populate MongoDB bravo.agencies document with config data using format in DB.md


###### Setup NodeJS & togeojson

If nodejs already installed as “node”, make symbolic link:
```
$ln -s /usr/bin/nodejs /usr/bin/node
```

Install togeojson
```
npm install -g togeojson
```



###### Google Service Account

1. For each agency, open Google Developer Console
2. Find Service Account
3. Generate JSON key
4. Add contents to MongoDB "agencies" collection under "oauth" key

###### Google Sheets

From Google Drive, create new Sheet named `Bravo Sheets` with worksheets `Routes`, `RFU`, `MPU`, `Signups`

From Google Drive, create new Script. Open it. Tools->Script Editor, copy the ID in URL.

Share the Bravo Library script with new user with View permissions.

Have the user open the Library in Script Editor, run a test function. 

Authorize permissions.

Share Bravo Sheets with new user with Edit permissions.

Have user open Bravo Sheets Script Editor, Resources->Libraries, paste in Bravo Library Project Key

Have user remove Bravo Library script from Google Drive.

Make sure user has all required Calendar's, Sheets, Gdrive Folders shared with them.

<br>
### Run Instructions

Start RabbitMQ daemon:

`$ rabbitmqctl start_app`

Run app:

`python run.py`

Arguments

-Start with celerybeat:

`-c, --celerybeat` 

-Start in debug mode:

`-d, --debug`

-Start in sandbox mode:

`-s, --sandbox`

<br>
### Shutdown Instructions

If running in foreground, kill with CTRL+C. This will kill Celery workers.

If running in background, get pid:

`$ps aux | grep -m 1 'python main.py' | awk '{print $2}'`

Now kill it using that PID:

`$kill -9 <PID>`

(May need to run twice)
