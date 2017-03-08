### Setup Instructions

#### Clone repository
```
git clone https://github.com/SeanEstey/Bravo --branch <b_name>
cd Bravo
```

#### Install Ubuntu Packages

Follow instructions in requirements/pkg_list.txt

#### Install Python Packages

Follow instructions in requirements/requirements.txt

#### Run setup

`python setup.py`

This will copy nginx virtual host file and setup logrotate.d

Add execution permission to Bravo/logs folder. 

Create empty files: celery.log, events.log, debug.log. Add execution permissions.

#### PHP Error Logging

Open /etc/php.ini

Find error_log line. Set:
`error_log = BRAVO_PATH/logs/debug.log`
Where BRAVO_PATH is the repository path.

#### Create MongoDB Auth File

Create "db_auth.py" in Bravo root directory:
```
user = "db_user"
password = "db_pw"
```

####Integrating Mailgun & Twilio

Update DNS records to point to IP address of VPS.
The Mailgun and Twilio webhooks use the domain name so they will point resolve to the new IP address once the DNS changes sync.

#####Mailgun 

1) Setup SMTP settings for Mailgun to send email on behalf of a domain
2) Set webhooks for domain: https://mailgun.com/app/webhooks:
	Delivered Messages: "http://www.bravoweb.ca/email/status"
	Dropped Messages: "http://www.bravoweb.ca/email/status"
	Hard Bounces: "http://www.bravoweb.ca/email/status"
	Spam Complaints: "http://www.bravoweb.ca/email/status"
	Unsubscribes: "http://www.bravoweb.ca/email/status"

#####Twilio

1) Setup a Phone number
2) Create Voice Preview app
	Tools->TwiML Apps
	Name
		"Voice Preview (Live Server)"
	Voice
		Request URL: "http://bravoweb.ca/notify/voice/preview"
2) Configure Phone number:
	Voice
		Configure With: "TwiML App"
		TwiML App: "Voice Preview (Live Server)"
	Messaging
		Configure With: "Webhooks/TwiML"
		A Message Comes In: "http://bravoweb.ca/alice/vec/receive"

####Setup MongoDB

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



##### Google Service Account

1. For each agency, open Google Developer Console
2. Find Service Account
3. Generate JSON key
4. Add contents to MongoDB "agencies" collection under "oauth" key

##### Google Sheets

From Google Drive, create new Sheet named `Bravo Sheets` with worksheets "Donations", "Issues", "Signups"

From Google Drive, create new Script. Open it. Tools->Script Editor, copy the ID in URL.

Share the Bravo Library script with new user with View permissions.

Have the user open the Library in Script Editor, run a test function. 

Authorize permissions.

Share Bravo Sheets with new user with Edit permissions.

Have user open Bravo Sheets Script Editor, Resources->Libraries, paste in Bravo Library Project Key

Have user remove Bravo Library script from Google Drive.

Make sure user has all required Calendar's, Sheets, Gdrive Folders shared with them.

#### SSL

Update config.py SSL_CERT_PATH="/path/to/chained_cert.crt"
Update virtualhost/default file variables: "ssl_certificate" and "ssl_certificate_key"

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
