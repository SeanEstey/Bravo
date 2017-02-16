'''app.__init__'''
import eventlet, pymongo, os, logging, socket, sys, time, requests
from flask import Flask, g
from flask_login import LoginManager
from flask_kvsession import KVSessionExtension
from celery import Celery, Task
from simplekv.db.mongo import MongoStore
from werkzeug.contrib.fixers import ProxyFix
import config, mongodb
from logger import file_handler
from utils import print_vars
from app.logger import DebugFilter, InfoFilter

eventlet.monkey_patch()

dbg_hdlr = file_handler(logging.DEBUG, 'debug.log')
inf_hdlr = file_handler(logging.INFO, 'events.log')
wrn_hdlr = file_handler(logging.WARNING, 'events.log')
err_hdlr = file_handler(logging.ERROR, 'events.log')
exc_hdlr = file_handler(logging.CRITICAL, 'events.log')
login_manager = LoginManager()
db_client = mongodb.create_client()
kv_store = MongoStore(db_client[config.DB], config.SESSION_COLLECTION)
kv_ext = KVSessionExtension(kv_store)

#-------------------------------------------------------------------------------
def get_keys(k=None, agcy=None):
    name = ''

    try:
        name = g.user.agency if g.user.is_authenticated else agcy
    except Exception as e:
        if not agcy:
            raise
        else:
            name = agcy

    conf = g.db.agencies.find_one({'name':name})

    if conf:
        if not k:
            return conf
        elif k in conf:
            return conf[k]
        else:
            raise Exception('key=%s not found'%k)
    else:
        raise Exception('no agency doc found ')

#-------------------------------------------------------------------------------
def create_app(pkg_name, kv_sess=True, testing=False):
    app = Flask(pkg_name)
    app.config.from_object(config)

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']

    app.logger.addHandler(dbg_hdlr)
    app.logger.addHandler(inf_hdlr)
    app.logger.addHandler(wrn_hdlr)
    app.logger.addHandler(err_hdlr)
    app.logger.addHandler(exc_hdlr)
    app.logger.setLevel(logging.DEBUG)

    for hdlr in app.logger.handlers:
        #print print_vars(hdlr)
        if hdlr.level == 10:
            app.logger.removeHandler(hdlr)

    from .auth.user import Anonymous
    login_manager.login_view = 'auth.show_login'
    login_manager.anonymous_user = Anonymous
    login_manager.init_app(app)

    if kv_sess:
        kv_ext.init_app(app)

    from app.main import endpoints
    from app.notify import endpoints

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
def init_celery(app):

    import celeryconfig
    celery.config_from_object(celeryconfig)
    celery.app = UberTask.flsk_app = app
    UberTask.db_client = mongodb.create_client(connect=False, auth=False)
    celery.Task = UberTask
    return celery

#-------------------------------------------------------------------------------
def get_logger(name):

    logger = logging.getLogger(name)
    logger.addHandler(dbg_hdlr)
    logger.addHandler(inf_hdlr)
    logger.addHandler(wrn_hdlr)
    logger.addHandler(err_hdlr)
    logger.addHandler(exc_hdlr)
    logger.setLevel(logging.DEBUG)
    return logger

#-------------------------------------------------------------------------------
def task_logger(name):

    from celery.utils.log import get_task_logger
    logger = get_task_logger(name)
    logger.addHandler(dbg_hdlr)
    logger.addHandler(inf_hdlr)
    logger.addHandler(wrn_hdlr)
    logger.addHandler(err_hdlr)
    logger.addHandler(exc_hdlr)
    logger.setLevel(logging.DEBUG)
    return logger

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
def get_server_prop():
    return {
        'TEST_SERVER': True if os.environ['BRV_TEST'] == 'True' else False,
        'SANDBOX_MODE': True if os.environ['BRV_SANDBOX'] == 'True' else False,
        'CELERY_BEAT': True if os.environ['BRV_BEAT'] == 'True' else False,
        'ADMIN': g.user.admin,
        'DEVELOPER': g.user.developer,
        'USER_NAME': g.user.name
    }

from app.socketio import smart_emit
from uber_task import UberTask

celery = Celery(__name__, broker='amqp://')
celery.Task = UberTask
