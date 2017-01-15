'''app.__init__'''

from celery import Celery, Task
import pymongo
import os
import logging
import socket
import requests
from datetime import timedelta
from flask import Flask, current_app, g, request, make_response, has_app_context, has_request_context
from flask_login import LoginManager
from flask_kvsession import KVSessionExtension
from simplekv.db.mongo import MongoStore
from werkzeug.contrib.fixers import ProxyFix
import config, mongodb
from utils import log_handler

deb_hand = log_handler(logging.DEBUG, 'debug.log')
inf_hand = log_handler(logging.INFO, 'info.log')
err_hand = log_handler(logging.ERROR, 'error.log')
exc_hand = log_handler(logging.CRITICAL, 'debug.log')

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

db_client = mongodb.create_client()
mongodb.authenticate(db_client)

kv_store = MongoStore(
    db_client[config.DB],
    config.SESSION_COLLECTION)
kv_ext = KVSessionExtension(kv_store)

log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get_db():
    if current_app and has_request_context():
        try:
            db = getattr(g, 'db')
        except Exception as e:
            return mongodb.create_client(connect=False, auth=True)[config.DB]
        else:
            return db

    return mongodb.create_client(connect=False, auth=True)[config.DB]

#-------------------------------------------------------------------------------
def get_keys(k=None, agency=None):
    conf = ''
    _agency = ''

    if current_user.is_authenticated:
        #if not getattr(g, 'conf'):
        #    if not getattr(g, 'db'):
        #        g.db = get_db()
        _agency = current_user.get_agency()
        conf = g.db.agencies.find_one({'name':_agency})
        #else:
        #    conf = g.conf
    else:
        if has_request_context():
            if session.get('conf'):
                conf = session.get('conf')
            elif session.get('agency'):
                conf = g.db.agencies.find_one({'name':session.get('agency')})
        else:
            if agency:
                db = get_db()
                conf = db.agencies.find_one({'name':agency})
            else:
                raise Exception('no req_context, no auth_user, no agency')

    if not conf:
        raise Exception('couldnt get conf')

    if k:
        return conf[k]
    else:
        return conf

#-------------------------------------------------------------------------------
def create_app(pkg_name):
    app = Flask(pkg_name)
    app.config.from_object(config)

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']

    app.logger.addHandler(err_hand)
    app.logger.addHandler(inf_hand)
    app.logger.addHandler(deb_hand)
    app.logger.setLevel(logging.DEBUG)

    login_manager.init_app(app)

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
def celery_app(app):
    celery = Celery(__name__, broker='amqp://')
    celery.config_from_object('celeryconfig')
    celery.conf.update(app.config)
    celery.app = app

    __all__ = ['RequestContextTask']

    class RequestContextTask(Task):
        abstract = True
        CONTEXT_ARG_NAME = '_flask_request_context'

        def __call__(self, *args, **kwargs):
            #with app.app_context():
            call = lambda: super(RequestContextTask, self).__call__(*args, **kwargs)

            context = kwargs.pop(self.CONTEXT_ARG_NAME, None)
            if context is None or has_request_context():
                return call()

            with app.test_request_context(**context):
                result = call()

                # process a fake "Response" so that
                # ``@after_request`` hooks are executed
                app.process_response(make_response(result or ''))

            return result

        def apply_async(self, args=None, kwargs=None, **rest):
            if rest.pop('with_request_context', True):
                self._include_request_context(kwargs)
            return super(RequestContextTask, self).apply_async(args, kwargs, **rest)

        def apply(self, args=None, kwargs=None, **rest):
            #if rest.pop('with_request_context', True):
            #    self._include_request_context(kwargs)
            return super(RequestContextTask, self).apply(args, kwargs, **rest)

        def retry(self, args=None, kwargs=None, **rest):
            #if rest.pop('with_request_context', True):
            #    self._include_request_context(kwargs)
            return super(RequestContextTask, self).retry(args, kwargs, **rest)

        def _include_request_context(self, kwargs):
            """Includes all the information about current Flask request context
            as an additional argument to the task.
            """
            if not has_request_context():
                return

            #log.debug('has_req_context')
            #log.debug(kwargs)

            # keys correspond to arguments of :meth:`Flask.test_request_context`
            context = {
                'path': request.path,
                'base_url': request.url_root,
                'method': request.method,
                'headers': dict(request.headers),
            }

            #log.debug(context)

            if '?' in request.url:
                context['query_string'] = request.url[(request.url.find('?') + 1):]

            kwargs[self.CONTEXT_ARG_NAME] = context

    celery.Task = RequestContextTask
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

    log.debug('task_emit %s', event)

    payload = {
        'event': event,
        'data':data
    }
    return requests.post('http://localhost/task_emit', json=payload)


