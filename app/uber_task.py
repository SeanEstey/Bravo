'''app.uber_task'''
import os
from celery import Task
from flask import g, has_app_context, has_request_context,\
make_response, request, current_app
from flask_login import login_user, current_user
from bson.objectid import ObjectId
from auth import user
from app.lib import mongodb
from app.lib.utils import print_vars
#from logging import getLogger
#log = getLogger('worker.%s'%__name__)

__all__ = ['UberTask']

class UberTask(Task):
    '''Preserves flask request and app contexts within the worker task.
    g.user: current_user
    g.db: new DB client + connection
    '''

    REQ_KW = '_flask_request_context'
    USERID_KW = '_user_id_oid'
    ENVIRON_KW = '_environ_var'
    flsk_app = None
    db_client = None
    buf_mongo_hndlr = None

    #---------------------------------------------------------------------------
    def __call__(self, *args, **kwargs):
        '''Called by worker
        '''

        req_ctx = has_request_context()
        app_ctx = has_app_context()
        call = lambda: super(UberTask, self).__call__(*args, **kwargs)
        context = kwargs.pop(self.REQ_KW, None)

        with self.flsk_app.app_context():
            if context:
                with self.flsk_app.test_request_context(**context):
                    current_app.config['SERVER_NAME'] = os.environ['BRV_DOMAIN']
                    self._load_context_vars(kwargs)
                    result = call()
                    self.flsk_app.process_response(make_response(result or ''))
                    return result
            else:
                with self.flsk_app.test_request_context():
                    current_app.config['SERVER_NAME'] = os.environ['BRV_DOMAIN']
                    self._load_context_vars(kwargs)
                    result = call()
                    self.flsk_app.process_response(make_response(''))
                    return result

        return result

    #---------------------------------------------------------------------------
    def apply(self, args=None, kwargs=None, **options):
        '''Called by Flask app
        '''

        #log.debug('apply args=%s, kwargs=%s, options=%s', args, kwargs, options)
        if options.pop('with_request_context', True) or has_app_context():
            self._push_contexts(kwargs)

        return super(UberTask, self).apply(args, kwargs, **options)

    #---------------------------------------------------------------------------
    def retry(self, args=None, kwargs=None, **options):
        '''Called by Flask app
        '''

        if options.pop('with_request_context', True) or has_app_context():
            self._push_contexts(kwargs)

        return super(UberTask, self).retry(args, kwargs, **options)

    #---------------------------------------------------------------------------
    def apply_async(self, args=None, kwargs=None, **rest):
        '''Called by Flask app. Wrapper for apply_async
        '''

        #log.debug('apply_async args=%s, kwargs=%s, rest=%s', args, kwargs, rest)
        if rest.pop('with_request_context', True) or has_app_context():
            self._push_contexts(kwargs)

        return super(UberTask, self).apply_async(args, kwargs, **rest)

    #---------------------------------------------------------------------------
    def _push_contexts(self, kwargs):
        '''Pass flask request/app context + flask.g vars into kwargs for worker task.
        '''

        # Save environ vars
        if has_app_context():
            if current_user:
                g.user = current_user

        kwargs[self.ENVIRON_KW] = {}

        for var in self.flsk_app.config['ENV_VARS']:
            kwargs[self.ENVIRON_KW][var] = os.environ.get(var, '')

        if has_request_context():
            if current_user.is_authenticated:
                kwargs[self.USERID_KW] = str(g.user._id)

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

        kwargs[self.REQ_KW] = context

    #---------------------------------------------------------------------------
    def _load_context_vars(self, kwargs):
        '''Called by worker. Load any request/app context + flask.g vars saved
        by _push_contexts
        '''

        env_vars = kwargs.pop(self.ENVIRON_KW, None)

        if env_vars:
            for k in env_vars:
                os.environ[k] = env_vars[k]

        g.db = self.db_client[self.flsk_app.config['DB']]
        mongodb.authenticate(self.db_client)

        user_oid = kwargs.pop(self.USERID_KW, None)

        if user_oid:
            db_user = g.db.users.find_one({'_id':ObjectId(str(user_oid))})
            login_user(user.User(
                db_user['user'],
                name=db_user['name'],
                _id=db_user['_id'],
                agency=db_user['agency'],
                admin=db_user['admin']))
            g.user = current_user
