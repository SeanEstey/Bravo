'''app/__init__.py'''

from celery import Celery
import pymongo
import logging
from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO, emit, send
from werkzeug.contrib.fixers import ProxyFix

import config

log_formatter = logging.Formatter('[%(asctime)s %(name)s] %(message)s','%m-%d %H:%M')

debug_handler = logging.FileHandler(config.LOG_PATH + 'debug.log')
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(log_formatter)

info_handler = logging.FileHandler(config.LOG_PATH + 'info.log')
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(log_formatter)

error_handler = logging.FileHandler(config.LOG_PATH + 'error.log')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_formatter)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

client = pymongo.MongoClient(
    host=config.MONGO_URL,
    port=config.MONGO_PORT,
    tz_aware=True,
    connect=False)

db = client[config.DB]


#celery = Celery(__name__, broker='amqp://')
#celery.config_from_object('celeryconfig')



#-------------------------------------------------------------------------------
def create_celery_app(app=None):
    app = app or create_app('app')
    celery = Celery(__name__, broker='amqp://')
    celery.config_from_object('celeryconfig')
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery

#-------------------------------------------------------------------------------
def create_app(pkg_name):
    app = Flask(pkg_name)
    app.config.from_object(config)

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.jinja_env.add_extension("jinja2.ext.do")

    app.logger.addHandler(error_handler)
    app.logger.addHandler(info_handler)
    app.logger.addHandler(debug_handler)
    app.logger.setLevel(logging.DEBUG)

    login_manager.init_app(app)

    from app.auth import auth as auth_mod
    from app.main import main as main_mod
    from app.notify import notify as notify_mod
    from app.routing import routing as routing_mod

    app.register_blueprint(auth_mod)
    app.register_blueprint(main_mod)
    app.register_blueprint(notify_mod)
    app.register_blueprint(routing_mod)

    '''absolute_url_adapter = app.url_map.bind_to_environ({
        'wsgi.url_scheme': 'http',
        'HTTP_HOST': app.config['SERVER_NAME'],
        'SCRIPT_NAME': '/notify',
        'REQUEST_METHOD': 'GET',
    })

    absolute_url_adapter.build('app.notify', force_external=True)
    '''

    #celery.conf.update(app.config)
    #celery.config_from_object('app.celeryconfig')

    return app

#-------------------------------------------------------------------------------
def create_db():
    client = pymongo.MongoClient(
        host=app.config['MONGO_URL'],
        port=app.config['MONGO_PORT'],
        tz_aware=True,
        connect=False)

    return client[app.config['DB']]
