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
flask_app.config.from_pyfile('config.py')
from werkzeug.contrib.fixers import ProxyFix
flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app)
#flask_app.wsgi_app = ReverseProxied(flask_app.wsgi_app)
flask_app.debug = DEBUG
flask_app.secret_key = SECRET_KEY
flask_app.jinja_env.add_extension("jinja2.ext.do")
socketio = SocketIO(flask_app)

mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT, connect=False)
db = mongo_client[DB_NAME]
logger = logging.getLogger(__name__)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(LOG_LEVEL)
handler.setFormatter(formatter)
logger.setLevel(LOG_LEVEL)
logger.addHandler(handler)

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

from scheduler import get_next_pickups, find_nps_in_schedule
from reminders import check_jobs, send_calls, send_emails, monitor_calls, cancel_pickup, set_no_pickup
from gsheets import process_receipts



