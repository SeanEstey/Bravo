import eventlet
# Allow for non-blocking standard library
#eventlet.monkey_patch()

import flask
from flask import Flask
import pymongo
import logging

from config import *

# Setup Loggers
log_formatter = logging.Formatter('[%(asctime)s %(name)s] %(message)s','%m-%d %H:%M')

debug_handler = logging.FileHandler(LOG_PATH + 'debug.log')
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(log_formatter)

info_handler = logging.FileHandler(LOG_PATH + 'info.log')
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(log_formatter)

error_handler = logging.FileHandler(LOG_PATH + 'error.log')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_formatter)

# Setup MongoDB
mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT, connect=False)
db = mongo_client[DB_NAME]

from flask_socketio import SocketIO
from flask.ext.socketio import *
from flask.ext.login import LoginManager

# Set up Flask Application
flask_app = Flask(__name__)
flask_app.config.from_pyfile('config.py')
from werkzeug.contrib.fixers import ProxyFix
flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app)
flask_app.debug = DEBUG
flask_app.secret_key = SECRET_KEY
flask_app.jinja_env.add_extension("jinja2.ext.do")
socketio = SocketIO(flask_app)

# Setup LoginManager Flask extension
login_manager = LoginManager()
login_manager.init_app(flask_app)
login_manager.login_view = PUB_URL + '/login'

flask_app.app_context().push()

import auth

#-------------------------------------------------------------------------------
@flask_app.before_request
def before_request():
    g.user = flask.ext.login.current_user

#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(username):
    return auth.load_user(username)

#-------------------------------------------------------------------------------
@socketio.on('disconnected')
def socketio_disconnected():
    logger.debug('socket disconnected')
    logger.debug(
    'num connected sockets: ' +
    str(len(socketio.server.sockets))
    )

#-------------------------------------------------------------------------------
@socketio.on('connected')
def socketio_connect():
    logger.debug(
        'num connected sockets: ' +
        str(len(socketio.server.sockets))
    )
    socketio.emit('msg', 'ping from ' + DB_NAME + ' server!');
