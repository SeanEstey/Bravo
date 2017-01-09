'''app.__init__'''

from celery import Celery
import pymongo
import os
import logging
import socket
import requests
from datetime import timedelta
from flask import Flask, current_app, g, has_app_context, has_request_context
from flask_login import LoginManager
from flask_kvsession import KVSessionExtension
from simplekv.db.mongo import MongoStore
from simplekv import KeyValueStore
from werkzeug.contrib.fixers import ProxyFix

import config
import mongodb

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

exception_handler = logging.FileHandler(config.LOG_PATH + 'error.log')
exception_handler.setLevel(logging.CRITICAL)
exception_handler.setFormatter(log_formatter)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

db_client = mongodb.create_client()

logger = logging.getLogger(__name__)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

#-------------------------------------------------------------------------------
def get_db():
    if current_app and has_request_context():
        return getattr(g, 'db')
    else:
        return mongodb.create_client(connect=True, auth=True)[config.DB]

#-------------------------------------------------------------------------------
def create_kv_session(app):
    store = MongoStore(
        db_client[config.DB],
        config.ALICE_SESSION_COLLECTION)
    return KVSessionExtension(store, app)

#-------------------------------------------------------------------------------
def create_app(pkg_name, db_client):
    app = Flask(pkg_name)
    app.config.from_object(config)

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']

    #timedelta(
    #    minutes=app.config['PERMANENT_SESSION_LIFETIME'])

    app.logger.addHandler(error_handler)
    app.logger.addHandler(info_handler)
    app.logger.addHandler(debug_handler)
    app.logger.setLevel(logging.DEBUG)

    login_manager.init_app(app)

    mongodb.authenticate(db_client)

    from app.auth import auth as auth_mod
    from app.main import main as main_mod
    from app.notify import notify as notify_mod
    from app.routing import routing as routing_mod
    from app.booker import booker as booker_mod
    from app.api import api as api_mod
    from app.alice import alice as alice_mod

    app.register_blueprint(auth_mod)
    app.register_blueprint(main_mod)
    app.register_blueprint(notify_mod)
    app.register_blueprint(routing_mod)
    app.register_blueprint(booker_mod)
    app.register_blueprint(api_mod)
    app.register_blueprint(alice_mod)

    return app

#-------------------------------------------------------------------------------
def create_celery_app(app):
    #app = app or create_app('app')

    celery = Celery(__name__, broker='amqp://')
    celery.config_from_object('celeryconfig')
    celery.conf.update(app.config)
    TaskBase = celery.Task

    #mongodb.auth(db_client)

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask

    return celery

#-------------------------------------------------------------------------------
def is_test_server():
    if os.environ.get('BRAVO_TEST_SERVER'):
        if os.environ['BRAVO_TEST_SERVER'] == 'True':
            return True
        else:
            return False

    # Don't know. Get IP and do reverse DNS lookup for domain

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("gmail.com",80))
    ip = s.getsockname()[0]
    s.close

    os.environ['BRAVO_HTTP_HOST'] = 'http://' + ip

    try:
        domain = socket.gethostbyaddr(ip)
    except Exception as e:
        print 'no domain registered. using twilio test server SMS number'
        os.environ['BRAVO_TEST_SERVER'] = 'True'
        return True

    if domain[0] == 'bravoweb.ca':
        print 'deploy server detected'
        os.environ['BRAVO_TEST_SERVER'] = 'False'
        return False

    print 'unknown domain found. assuming test server'
    os.environ['BRAVO_TEST_SERVER'] = 'True'
    return True

#-------------------------------------------------------------------------------
def config_test_server(source):
    # Swap out any sandbox credentials that may be present

    db = get_db()
    #test_db = client['test']
    agencies = db.agencies.find()
    #cred = test_db.credentials.find_one()

    if source == 'sandbox':
        os.environ['BRAVO_SANDBOX_MODE'] = 'True'
    else:
        os.environ['BRAVO_SANDBOX_MODE'] = 'False'

    '''
    for agency in agencies:
        db.agencies.update_one(
            {'name': agency['name']},
            {'$set':{
                'twilio': cred['twilio'][source]
            }})
    '''

    # Set SmsUrl callback to point to correct server
    #https://www.twilio.com/docs/api/rest/incoming-phone-numbers#instance
    return True

#-------------------------------------------------------------------------------
def task_emit(event, data):
    '''Used by celery worker to send SocketIO messages'''

    logger.debug('task_emit %s', event)

    payload = {
        'event': event,
        'data':data
    }
    return requests.post('http://localhost/task_emit', json=payload)
