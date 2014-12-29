Instructions<br>

Clone repository
```
git clone https://github.com/SeanEstey/Bravo
cd Bravo
```
Start celery worker<br>
`./celery.sh`
Server<br>
-Flask server running on http://localhost:8000<br>
-Nginx running flask server as reverse proxy (see nginx .conf file in /config)<br>
Start Flask server<br>
`python server.py`<br>
Register schedule monitor process<br>
`crontab -e`<br>
Add following line<br>
`@hourly /usr/bin/python /root/bravo/scheduler.py`<br>

To manually shutdown server running in background<br>
get pid<br>
`ps aux | grep -m 1 'python server.py' | awk '{print $2}'`<br>
Kill it<br>
`kill -9 <PID>`<br>

(May need to run twice)
