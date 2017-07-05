'''app.__init__'''
import logging, os
from flask import Flask, g, session, has_app_context, has_request_context
from flask_login import LoginManager
from celery import Celery

# GLOBALS

login_manager = LoginManager()
celery = Celery(__name__, broker='amqp://')
from uber_task import UberTask
celery.Task = UberTask

# CLASSES

class DebugFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.DEBUG
class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO
class WarningFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.WARNING
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

# METHODS

#-------------------------------------------------------------------------------
def get_keys(k=None, group=None):
    '''Find user group configuration document
    @k: sub-document key
    @group: user group name'''

    name = None

    if group is not None:
        name = group
    else:
        if g.get('group'):
            name = g.group
        elif g.get('user') and g.user.is_authenticated:
            name = g.group

    if name is None:
        raise Exception('no user group found in get_keys')

    conf = g.db['groups'].find_one({'name':name})

    if conf is None:
        raise Exception('no doc found for name=%s' % name)
    if k and k not in conf:
        raise Exception('key=%s not found' % k)

    return conf if not k else conf[k]

#-------------------------------------------------------------------------------
def get_group():
    '''Find user group name'''

    if has_app_context():
        if g.get('group'):
            return g.get('group')
        elif g.get('user'):
            return g.get('user').group
        elif has_request_context():
            if session.get('group'):
                return session['group']

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
def get_server_prop():
    return {
        'TEST_SERVER': True if os.environ['BRV_TEST'] == 'True' else False,
        'SANDBOX_MODE': True if os.environ['BRV_SANDBOX'] == 'True' else False,
        'CELERY_BEAT': True if os.environ['BRV_BEAT'] == 'True' else False,
        'ADMIN': g.user.admin,
        'DEVELOPER': g.user.developer,
        'USER_NAME': g.user.name
    }

#-------------------------------------------------------------------------------
def create_app(pkg_name, kv_sess=True, mongo_client=True):

    from werkzeug.contrib.fixers import ProxyFix
    from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
    from app.lib.mongo_logger import _connection, BufferedMongoHandler
    from config import LOG_PATH as path
    import config

    app = Flask(pkg_name)
    app.config.from_object(config)
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']

    if mongo_client:
        from app.lib import mongo
        from db_auth import user, password
        app.db_client = mongo.create_client()

        mongo_handler = BufferedMongoHandler(
            level=DEBUG,
            client=app.db_client,
            connect=True,
            db_name='bravo',
            user=user,
            pw=password)
        app.logger.addHandler(mongo_handler)
        mongo_handler.init_buf_timer()

    if kv_sess:
        from simplekv.db.mongo import MongoStore
        from flask_kvsession import KVSessionExtension
        kv_store = MongoStore(app.db_client[config.DB], config.SESSION_COLLECTION)
        kv_ext = KVSessionExtension(kv_store)
        kv_ext.init_app(app)
        app.kv_ext = kv_ext
        app.kv_store = kv_store

    # Flask App Logger & Handlers
    app.logger.setLevel(DEBUG)

    app.logger.addHandler(file_handler(DEBUG,
        '%sdebug.log'%path,
        color=colors.WHITE))
    app.logger.addHandler(file_handler(INFO,
        '%sevents.log'%path,
        color=colors.GRN))
    app.logger.addHandler(file_handler(WARNING,
        '%sevents.log'%path,
        color=colors.YLLW))
    app.logger.addHandler(file_handler(ERROR,
        '%sevents.log'%path,
        color=colors.RED))

    # Flask-Login ext.

    from .auth.user import Anonymous
    login_manager.login_view = 'auth.show_login'
    login_manager.anonymous_user = Anonymous
    login_manager.init_app(app)
    app.login_manager = login_manager

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

#---------------------------------------------------------------------------
def file_handler(level, file_path,
                 fmt=None, datefmt=None, color=None, name=None):

    handler = logging.FileHandler(file_path)
    handler.setLevel(level)

    if name is not None:
        handler.name = name
    else:
        handler.name = 'lvl_%s_file_handler' % str(level)

    if level == logging.DEBUG:
        handler.addFilter(DebugFilter())
    elif level == logging.INFO:
        handler.addFilter(InfoFilter())
    elif level == logging.WARNING:
        handler.addFilter(WarningFilter())

    formatter = logging.Formatter(
        colors.BLUE + (fmt or '[%(asctime)s %(name)s %(processName)s]: ' + colors.ENDC + color + '%(message)s') + colors.ENDC,
        (datefmt or '%m-%d %H:%M'))

    handler.setFormatter(formatter)
    return handler
