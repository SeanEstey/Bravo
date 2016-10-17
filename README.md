### Setup Instructions

###### Clone repository
```
git clone https://github.com/SeanEstey/Bravo
cd Bravo
```

###### Run setup

`python setup.py`

Set proper webroot permissions for www-data user:
```
chown -R root:www-data /var/www/bravo
chmod -R 660 /var/www/bravo
```

###### Mongo Logins
```
$mongo
>> use bravo
>> db.logins.insert({
  'agency': 'name'
  'user': 'name', 
  'password': 'pw',
  'admin': 'true/false'
})
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
