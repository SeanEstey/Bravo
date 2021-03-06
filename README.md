# Overview

Bravo runs on Ubuntu 16.04, with core dependencies being MongoDB 3.2+, nginx, python 2.7 with celery.

It relies heavily on asynchronous background tasks via celery, so a system with multiple CPU cores is ideal.

# End User Manual

[https://docs.google.com/document/d/1uiN0v5ax0lxBXCGAFy9Er1f_pup6McUAhhDt8d4_Ccw/edit?usp=sharing](Bravo User Guide)

# Instructions for Clean Install on New VPS

-Setup VPS w/ Ubuntu 16.04 LTS (and mongodb 3.2 if possible)

-Clone repository:

	```
	git clone https://github.com/SeanEstey/Bravo --branch <b_name>
	cd Bravo
	```

-Update your DNS records for the new IP address

-Install Python 2.7

-Install mongodb 3.2

-Install other dependencies from requirements/pkg_list.txt and requirements/requirements.txt

-Run setup.py

Virtual host and logrotate.d will be setup now.

-Setup SSL:

    -Update config.py SSL_CERT_PATH="/path/to/chained_cert.crt"  

    -Update virtualhost/default file variables: "ssl_certificate" and "ssl_certificate_key"  

-Add execution permission to Bravo/logs folder

-Setup PHP logging:

    -Open /etc/php.ini

    -Find error_log line and replace this line:

    'error_log = BRAVO_PATH/logs/debug.log'

    Where BRAVO_PATH is the repository path.

#### Mailgun Setup

(1) Setup SMTP settings for Mailgun to send email on behalf of a domain  
(2) Set webhooks for domain: https://mailgun.com/app/webhooks:  
  * Delivered Messages: "http://www.bravoweb.ca/email/status"  
  * Dropped Messages: "http://www.bravoweb.ca/email/status"  
  * Hard Bounces: "http://www.bravoweb.ca/email/status"  
  * Spam Complaints: "http://www.bravoweb.ca/email/status"  
  * Unsubscribes: "http://www.bravoweb.ca/email/status"  

#### Twilio Setup

The Mailgun and Twilio webhooks use the domain name so they will point resolve to the new IP address once the DNS changes sync.

Setup a Phone number  
Create Voice Preview app  
  * Tools->TwiML Apps  
    * Name  
      * "Voice Preview (Live Server)"  
    * Voice  
      * Request URL: "http://bravoweb.ca/notify/voice/preview"  
Configure Phone number   
  * Voice  
    * Configure With: "TwiML App"  
    * TwiML App: "Voice Preview (Live Server)"  
  * Messaging  
    * Configure With: "Webhooks/TwiML"  
    * A Message Comes In: "http://bravoweb.ca/alice/vec/receive"  

#### MongoDB Setup

Create database named "bravo"  
Create collections: "users", "agencies", "maps"  
Populate MongoDB bravo.agencies document with config data using format in DB.md  
Create "db_auth.py" in Bravo root directory:  

```
user = "db_user"
password = "db_pw"
```

#### Google Service Account Setup

1. For each agency, open Google Developer Console  
2. Find Service Account  
3. Generate JSON key  
4. Add contents to MongoDB "agencies" collection under "oauth" key  

#### Bravo Sheets Setup

From Google Drive, create new Sheet named `Bravo Sheets` with worksheets "Donations", "Issues", "Signups"  
From Google Drive, create new Script. Open it. Tools->Script Editor, copy the ID in URL.  
Share the Bravo Library script with new user with View permissions.  
Have the user open the Library in Script Editor, run a test function.  
Authorize permissions.  
Share Bravo Sheets with new user with Edit permissions.  
Have user open Bravo Sheets Script Editor, Resources->Libraries, paste in Bravo Library Project Key  
Have user remove Bravo Library script from Google Drive.  
Make sure user has all required Calendar's, Sheets, Gdrive Folders shared with them.  

# Bravo Startup Instructions

-Make sure mongod is running
-If not, start with:
	`$ mongod --auth --port 27017 --dbpath /var/lib/mongodb`
-Start RabbitMQ daemon:
	`$ rabbitmqctl start_app`

-Run run.py (with appropriate cmd-line args)
	`-c, --celerybeat`
	`-d, --debug`
	`-s, --sandbox`


# Bravo Shutdown Instructions

If running in foreground, kill with CTRL+C. This will kill Celery workers.

If running in background, get pid:

`$ps aux | grep -m 1 'python main.py' | awk '{print $2}'`

Now kill it using that PID:

`$kill -9 <PID>`

(May need to run twice)

# Notes

To free memory not released by abberant python/celery processes:

$ sync && echo 3 | sudo tee /proc/sys/vm/drop_caches


# System Maintenance

All system events are logged to MongoDB. They can be accessed within Bravo via the Admin menu-->Recent lower menu.

Logging events are also recorded to logfiles in ~/Bravo/logs/. Logrotate.d is set to auto-rotate and keeps 1 week of logfiles by default.
