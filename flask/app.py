import eventlet
# Allow for non-blocking standard library
#eventlet.monkey_patch()

import flask
from flask import Flask
from flask.ext.login import LoginManager
from flask_socketio import SocketIO
import pymongo
import logging

from celery import Celery
from reverse_proxy import ReverseProxied
from flask.ext.socketio import *
from config import *

flask_app = Flask(__name__)
mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT, connect=False)
db = mongo_client[DB_NAME]

log_formatter = logging.Formatter('[%(asctime)s %(name)s] %(message)s','%m-%d %H:%M')
log_handler = logging.FileHandler(LOG_FILE)
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(log_formatter)

flask_app.config.from_pyfile('config.py')
from werkzeug.contrib.fixers import ProxyFix
flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app)
flask_app.debug = DEBUG
flask_app.secret_key = SECRET_KEY
flask_app.jinja_env.add_extension("jinja2.ext.do")

rlh = logging.handlers.TimedRotatingFileHandler(LOG_FILE, when='midnight', interval=1)
flask_app.logger.addHandler(rlh)
flask_app.logger.setLevel(logging.DEBUG)
socketio = SocketIO(flask_app)

login_manager = LoginManager()
login_manager.init_app(flask_app)
login_manager.login_view = PUB_URL + '/login' #url_for('login')

def make_celery(app):
    celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

celery_app = make_celery(flask_app)
celery_app.config_from_object('config')

flask_app.app_context().push()

#from reminders import check_jobs, send_calls, send_emails, monitor_calls, cancel_pickup, set_no_pickup
from receipts import process
from gsheets import add_signup
#from scheduler import analyze_non_participants
