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

May have to add execution permissions to log files created in /var/www/bravo/logs for PHP script.

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
