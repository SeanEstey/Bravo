<h2>Instructions</h2><br>

Install Dependencies<br>
```
apt-get install python-pip python-dev mongodb nginx
pip install celery flask flask-socketio pymongo
```
Clone repository<br>
```
git clone https://github.com/SeanEstey/Bravo
cd Bravo
```
Start celery worker<br>
`./celery.sh`<br>

Start Flask Server:<br>
`python server.py <mode>`<br>

mode == 'test' runs on http://localhost:5000<br>
mode == 'deploy' runs on http://localhost:8000<br>

Setup front end server to redirect to proper proxy addresses (see /config for Nginx .conf file)<br>

To manually shutdown server running in background<br>
get pid<br>
`ps aux | grep -m 1 'python server.py' | awk '{print $2}'`<br>
Kill it<br>
`kill -9 <PID>`<br>
(May need to run twice)
