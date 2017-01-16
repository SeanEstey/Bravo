'''app.__init__'''

from celery import Celery, Task
import pymongo
import eventlet
import os
import logging
import socket
import requests
from datetime import timedelta
from flask import Flask, current_app, g, request, make_response, has_app_context, has_request_context
from flask_login import LoginManager

from flask_kvsession import KVSessionExtension
from flask_socketio import SocketIO
from simplekv.db.mongo import MongoStore
from werkzeug.contrib.fixers import ProxyFix
import config, mongodb
from utils import log_handler, print_vars

eventlet.monkey_patch()

deb_hand = log_handler(logging.DEBUG, 'debug.log')
inf_hand = log_handler(logging.INFO, 'info.log')
err_hand = log_handler(logging.ERROR, 'error.log')
exc_hand = log_handler(logging.CRITICAL, 'debug.log')

login_manager = LoginManager()


db_client = mongodb.create_client()
mongodb.authenticate(db_client)
task_db_client = mongodb.create_client()

kv_store = MongoStore(
    db_client[config.DB],
    config.SESSION_COLLECTION)
kv_ext = KVSessionExtension(kv_store)

log = logging.getLogger(__name__)

sio_app = SocketIO()

#-------------------------------------------------------------------------------
def get_db():
    if has_app_context():
        return g.db
    else:
        return db_client[config.DB]

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
def create_app(pkg_name, kv_sess=True):
    #log.debug('creating app')

    app = Flask(pkg_name)
    app.config.from_object(config)
    app.clients = {}

    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.permanent_session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']

    app.logger.addHandler(err_hand)
    app.logger.addHandler(inf_hand)
    app.logger.addHandler(deb_hand)
    app.logger.setLevel(logging.DEBUG)

    from .auth.user import Anonymous
    login_manager.login_view = 'auth.login'
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
def celery_app(app):
    celery = Celery(__name__, broker='amqp://')
    celery.config_from_object('celeryconfig')
    celery.conf.update(app.config)
    celery.app = app

    __all__ = ['RequestContextTask']

    class RequestContextTask(Task):
        CONTEXT_ARG_NAME = '_flask_request_context'

        def __call__(self, *args, **kwargs):
            '''Called by worker'''

            call = lambda: super(RequestContextTask, self).__call__(*args, **kwargs)
            context = kwargs.pop(self.CONTEXT_ARG_NAME, None)

            if context is None or has_request_context():
                if not has_app_context():
                    with app.app_context():
                        g.db = task_db_client['bravo']
                        mongodb.authenticate(task_db_client)
                        print '__call__ app_ctx=%s, req_ctx=%s, db=%s'%(has_app_context(), has_request_context(), g.db!=None)

                        return call()
                else:
                    g.db = task_db_client['bravo']
                    mongodb.authenticate(task_db_client)
                    print '__call__ app_ctx=%s, req_ctx=%s, db=%s'%(has_app_context(), has_request_context(), g.db!=None)

                    return call()

            with app.test_request_context(**context):
                g.db = task_db_client['bravo']
                mongodb.authenticate(task_db_client)
                print '__call__ app_ctx=%s, req_ctx=%s, db=%s'%(has_app_context(), has_request_context(), g.db!=None)

                result = call()
                # process a fake "Response" so that
                # ``@after_request`` hooks are executed
                app.process_response(make_response(result or ''))

            return result

        def apply_async(self, args=None, kwargs=None, task_id=None, producer=None, link=None, link_error=None, shadow=None, **options):
            '''Called by Flask app'''
            print 'apply_async'

            #log.debug('apply_async | name=%s, args=%s, kwargs=%s, producer=%s, link=%s, shadow=%s, options=%s',
            #    self.name, args, kwargs, producer, link, shadow, options)
            if options.pop('with_request_context', True):
                self._include_request_context(kwargs)
            return super(RequestContextTask, self).apply_async(args, kwargs, task_id, producer, link, link_error, shadow, **options)

        def apply(self, args=None, kwargs=None, **options):
            '''Called by Flask app'''
            if options.pop('with_request_context', True):
                self._include_request_context(kwargs)
            return super(RequestContextTask, self).apply(args, kwargs, **options)

        def retry(self, args=None, kwargs=None, **options):
            '''Called by Flask app'''
            if options.pop('with_request_context', True):
                self._include_request_context(kwargs)
            return super(RequestContextTask, self).retry(args, kwargs, **options)

        def _include_request_context(self, kwargs):
            """Includes all the information about current Flask request context
            as an additional argument to the task.
            """

            if not has_request_context():
                return

            # keys correspond to arguments of :meth:`Flask.test_request_context`
            context = {
                'path': request.path,
                'base_url': request.url_root,
                'method': request.method,
                'headers': dict(request.headers),
            }

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

    #log.debug('task_emit %s', event)

    r = requests.post(
        'http://localhost/task_emit',
        json= {
            'event': event,
            'data':data})

    #log.debug(r)
