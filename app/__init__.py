'''app.__init__'''
import eventlet, os
from flask import Flask, g, session, has_app_context, has_request_context
from flask_login import LoginManager
from flask_kvsession import KVSessionExtension
from celery import Celery, Task
from simplekv.db.mongo import MongoStore
from werkzeug.contrib.fixers import ProxyFix
import config
from app.lib import mongodb
from app.lib.utils import print_vars

eventlet.monkey_patch()

login_manager = LoginManager()
db_client = mongodb.create_client()
kv_store = MongoStore(db_client[config.DB], config.SESSION_COLLECTION)
kv_ext = KVSessionExtension(kv_store)

from app.lib.loggy import Loggy

class colors:
    BLUE = '\033[94m'
    GRN = '\033[92m'
    YLLW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[37m'
    ENDC = '\033[0m'
    HEADER = '\033[95m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


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
def get_group():
    if has_app_context():
        if g.get('group'):
            return g.get('group')
        elif g.get('user'):
            return g.get('user').agency
        else:
            return 'sys'
    elif has_request_context():
        if session.get('agcy'):
            return session['agcy']
        else:
            return 'sys'
    else:
        return 'sys'

#-------------------------------------------------------------------------------
def get_username():
    # Bravo user
    if has_app_context() and g.get('user'):
        return g.get('user').user_id
    elif has_request_context():
        # Reg. end-user using Alice
        if session.get('account'):
            return session['account']['id']
        # Unreg. end-user using Alice
        elif session.get('anon_id'):
            return session['anon_id']
        # Celery task w/ req ctx
        else:
            return 'sys'
    # System task
    else:
        return 'sys'

#-------------------------------------------------------------------------------
def create_app(pkg_name, kv_sess=True, testing=False):

    from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

    app = Flask(pkg_name)
    app.config.from_object(config)

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']

    # Loggers

    for hdlr in app.logger.handlers:
        if hdlr.level == DEBUG:
            app.logger.removeHandler(hdlr)
    app.logger.addHandler(Loggy.inf_hdlr)
    app.logger.addHandler(Loggy.wrn_hdlr)
    app.logger.addHandler(Loggy.err_hdlr)
    app.logger.addHandler(create_buf_mongo_hndlr(INFO))
    app.logger.setLevel(DEBUG)

    king_app_logger = create_mongo_logger(app.config['APP_ROOT_LOGGER_NAME'], DEBUG)
    king_celery_logger = create_mongo_logger(app.config['CELERY_ROOT_LOGGER_NAME'], INFO)

    # Flask-Login ext.

    from .auth.user import Anonymous
    login_manager.login_view = 'auth.show_login'
    login_manager.anonymous_user = Anonymous
    login_manager.init_app(app)

    if kv_sess:
        kv_ext.init_app(app)

    # Blueprints

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
def create_buf_mongo_hndlr(level):

    from app.lib.mongo_log import BufferedMongoHandler
    from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
    import db_auth

    return BufferedMongoHandler(
        level = level,
        connect=False,
        user=db_auth.user,
        pw=db_auth.password,
        db_name='bravo',
        coll='buffer',
        auth_db_name='admin',
        capped=True,
        cap_max=10000,
        cap_size=10000000,
        buf_size=50,
        buf_flush_tim=5.0,
        buf_flush_lvl=ERROR)

#-------------------------------------------------------------------------------
def create_mongo_logger(name, level):

    import sys
    from logging import getLogger, StreamHandler, DEBUG, INFO, WARNING, ERROR, CRITICAL

    stream_hndlr = StreamHandler(sys.stdout)
    stream_hndlr.setLevel(DEBUG)

    log = getLogger(name)
    log.setLevel(level)
    log.addHandler(stream_hndlr)
    log.addHandler(create_buf_mongo_hndlr(level))
    log.addHandler(Loggy.dbg_hdlr)
    log.addHandler(Loggy.inf_hdlr)
    log.addHandler(Loggy.wrn_hdlr)
    log.addHandler(Loggy.err_hdlr)

    return log

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

from app.main.socketio import smart_emit
from uber_task import UberTask

celery = Celery(__name__, broker='amqp://')
celery.Task = UberTask

