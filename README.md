<h2>Instructions</h2><br>

Install Dependencies<br>
```
apt-get install python-pip python-dev mongodb nginx rabbitmq-server
pip install celery flask flask-socketio pymongo python-dateutil twilio
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
DB_NAME = 'test'
LOCAL_PORT = 5000
LOCAL_URL = 'http://localhost:5000'
PUB_URL = 'http://seanestey.ca:8080/bravo'
TITLE = 'Bravo:8080'
```

Setup front end server to redirect to proper proxy addresses (see /config for Nginx .conf file)<br>

To manually shutdown server running in background<br>
get pid<br>
`ps aux | grep -m 1 'python server.py' | awk '{print $2}'`<br>
Kill it<br>
`kill -9 <PID>`<br>
(May need to run twice)
