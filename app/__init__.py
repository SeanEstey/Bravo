import eventlet
# Allow for non-blocking standard library
#eventlet.monkey_patch()
from celery import Celery

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
app.config.from_object('config')
app.wsgi_app = ProxyFix(app.wsgi_app)
app.jinja_env.add_extension("jinja2.ext.do")
app.logger.addHandler(error_handler)
app.logger.addHandler(info_handler)
app.logger.addHandler(debug_handler)
app.logger.setLevel(logging.DEBUG)

# Setup Socket.io
socketio = SocketIO(app)

celery_app = Celery(include=['app.tasks'])
celery_app.config_from_object('app.celeryconfig')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = app.config['PUB_URL'] + '/login'

# Setup pymongo with timezone-awareness
import pymongo

client = pymongo.MongoClient(
    host=app.config['MONGO_URL'],
    port=app.config['MONGO_PORT'],
    tz_aware=True,
    connect=False)

db = client[app.config['DB']]


from app.api.views import api as api_module
from app.main.views import main as main_module
from app.notify.views import notify as notify_module
from app.routing.views import routing as routing_module

app.register_blueprint(api_module)
app.register_blueprint(main_module)
app.register_blueprint(notify_module)
app.register_blueprint(routing_module)


from app.main import auth

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
