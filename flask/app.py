import eventlet
# Allow for non-blocking standard library
#eventlet.monkey_patch()

from config import LOG_PATH

# Setup Loggers
import logging

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


# Set up Flask Application
import flask
from flask import Flask, g
from flask.ext.login import LoginManager
from flask_socketio import SocketIO
from flask_socketio import send, emit
from werkzeug.contrib.fixers import ProxyFix

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.wsgi_app = ProxyFix(app.wsgi_app)
app.jinja_env.add_extension("jinja2.ext.do")
app.logger.addHandler(error_handler)
app.logger.addHandler(info_handler)
app.logger.addHandler(debug_handler)
app.logger.setLevel(logging.DEBUG)

# Setup Socket.io
socketio = SocketIO(app)

# Setup LoginManager Flask extension
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = app.config['PUB_URL'] + '/login'

# TODO: What does this do again????
app.app_context().push()

# Setup MongoDB
import pymongo

mongo_client = pymongo.MongoClient(app.config['MONGO_URL'], app.config['MONGO_PORT'], connect=False)
db = mongo_client[app.config['DB']]

import auth

#-------------------------------------------------------------------------------
@app.before_request
def before_request():
    g.user = flask.ext.login.current_user

#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(username):
    return auth.load_user(username)

#-------------------------------------------------------------------------------
@socketio.on('disconnect')
def socketio_disconnected():
    app.logger.debug('socket disconnected')

    #app.logger.debug(
    #'num connected sockets: ' +
    #str(len(socketio.server.sockets))
    #)

#-------------------------------------------------------------------------------
@socketio.on('connect')
def socketio_connect():
    app.logger.debug('socket.io connected')

    #app.logger.debug(
    #    'num connected sockets: ' +
    #    str(len(socketio.server.sockets))
    #)
    #socketio.emit('msg', 'ping from server!');

    emit('connected')
