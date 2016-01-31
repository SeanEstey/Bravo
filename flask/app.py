import flask
from flask import Flask,render_template,request,g,Response,redirect,url_for
from flask.ext.login import LoginManager, login_user, logout_user, current_user, login_required
from flask.ext.socketio import *
import pymongo
import logging

from celery import Celery
from reverse_proxy import ReverseProxied
from server_settings import *
from flask.ext.socketio import *
from config import *

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.debug = DEBUG
app.secret_key = SECRET_KEY
app.jinja_env.add_extension("jinja2.ext.do")
socketio = SocketIO(app)

celery_app = Celery('tasks')
celery_app.config_from_object('config')

mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT, connect=False)
db = mongo_client[DB_NAME]
logger = logging.getLogger(__name__)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(LOG_LEVEL)
handler.setFormatter(formatter)
logger.setLevel(LOG_LEVEL)
logger.addHandler(handler)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = PUB_URL + '/login' #url_for('login')


