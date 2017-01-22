'''app.__init__'''

from celery import Celery, Task
import pymongo
import eventlet
import os
import logging
import socket
import requests
from bson.objectid import ObjectId
from datetime import timedelta
from flask import Flask, current_app, g, has_app_context, has_request_context
from flask_login import LoginManager, current_user
from flask_kvsession import KVSessionExtension
from flask_socketio import SocketIO, rooms
from simplekv.db.mongo import MongoStore
from werkzeug.contrib.fixers import ProxyFix
import config, mongodb
from utils import log_handler, print_vars
from app.sio import smart_emit

eventlet.monkey_patch()

deb_hand = log_handler(logging.DEBUG, 'debug.log')
inf_hand = log_handler(logging.INFO, 'info.log')
err_hand = log_handler(logging.ERROR, 'error.log')
exc_hand = log_handler(logging.CRITICAL, 'debug.log')
log = logging.getLogger(__name__)
login_manager = LoginManager()
db_client = mongodb.create_client()
mongodb.authenticate(db_client)
kv_store = MongoStore(
    db_client[config.DB],
    config.SESSION_COLLECTION)
kv_ext = KVSessionExtension(kv_store)

from uber_task import UberTask
celery = Celery(__name__, broker='amqp://')
celery.Task = UberTask

#-------------------------------------------------------------------------------
def get_db():
    if has_app_context():
        return g.db
    else:
        return db_client[config.DB]

#-------------------------------------------------------------------------------
def get_keys(k, agcy=None):
    if g.user.is_authenticated:
        name = g.user.agency
    elif agcy:
        name = agcy
    else:
        raise Exception('no key or agency available')

    conf = g.db.agencies.find_one({'name':name})

    if conf and k in conf:
        return conf[k]
    else:
        return None

#-------------------------------------------------------------------------------
def create_app(pkg_name, kv_sess=True, testing=False):
    app = Flask(pkg_name)
    app.config.from_object(config)
    app.clients = {}
    app.testing = testing

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']

    app.logger.addHandler(err_hand)
    app.logger.addHandler(inf_hand)
    app.logger.addHandler(deb_hand)
    app.logger.setLevel(logging.DEBUG)

    from .auth.user import Anonymous
    login_manager.login_view = 'auth.show_login'
    login_manager.anonymous_user = Anonymous
    login_manager.init_app(app)

    if kv_sess:
        kv_ext.init_app(app)

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
def init_celery(celery, app):
    import celeryconfig
    from celery.utils.log import get_task_logger

    celery = Celery(__name__, broker='amqp://')
    celery.config_from_object(celeryconfig)
    celery.app = UberTask.flsk_app = app
    UberTask.db_client = mongodb.create_client()
    celery.Task = UberTask

    logger = get_task_logger(__name__)
    logger.addHandler(err_hand)
    logger.addHandler(inf_hand)
    logger.addHandler(deb_hand)
    logger.addHandler(exc_hand)
    logger.setLevel(logging.DEBUG)

    return celery

#-------------------------------------------------------------------------------
def clean_expired_sessions():
    '''
    from app import kv_ext
    try:
        with current_app.test_request_context():
            log.info('cleaning expired sessions')
            log.debug(utils.print_vars(kv_ext))
            kv_ext.cleanup_sessions()
    except Exception as e:
        log.debug(str(e))
    '''
    pass

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
