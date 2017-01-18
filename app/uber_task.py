'''app.uber_task'''

import mongodb
from celery import Task
from flask import current_app, g, has_app_context, has_request_context,\
make_response, request
from flask_login import login_user, current_user
from bson.objectid import ObjectId
from auth import user

__all__ = ['UberTask']

class UberTask(Task):
    '''Preserves flask request and app contexts within the worker task.
    g.user: current_user
    g.db: new DB client + connection
    '''

    REQ_ARG_NAME = '_flask_request_context'
    USERID_ARG_NAME = '_user_id_oid'
    flsk_app = None
    db_client = None

    #---------------------------------------------------------------------------
    def __call__(self, *args, **kwargs):
        '''Called by worker
        '''

        #print '__call__'
        req_ctx = has_request_context()
        app_ctx = has_app_context()
        call = lambda: super(UberTask, self).__call__(*args, **kwargs)
        context = kwargs.pop(self.REQ_ARG_NAME, None)

        if context is None or req_ctx:
            if not app_ctx:
                with self.flsk_app.app_context():
                    self._load_context_vars(kwargs)
                    return call()
            else:
                self._load_context_vars(kwargs)
                return call()

        with self.flsk_app.test_request_context(**context):
            self._load_context_vars(kwargs)
            result = call()
            self.flsk_app.process_response(make_response(result or ''))

        return result

    #---------------------------------------------------------------------------
    def apply(self, args=None, kwargs=None, **options):
        '''Called by Flask app
        '''

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
    def async(self, args=None, kwargs=None, task_id=None, producer=None,
        link=None, link_error=None, shadow=None, **options):
        '''Called by Flask app. Wrapper for apply_async which adds 'queue' kwarg
        '''

        if options.pop('with_request_context', True) or has_app_context():
            self._push_contexts(kwargs)

        options['queue'] = self.flsk_app.config['DB']

        return super(UberTask, self).apply_async(args, kwargs, task_id, producer,
            link, link_error, shadow, **options)

    #---------------------------------------------------------------------------
    def _push_contexts(self, kwargs):
        '''If request context, saves data to kwargs for setup on __call__
        If app context, push current_user._id to kwargs also
        '''

        if has_app_context():
            kwargs[self.USERID_ARG_NAME] = str(g.user._id)

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

        kwargs[self.REQ_ARG_NAME] = context

    #---------------------------------------------------------------------------
    def _load_context_vars(self, kwargs):
        '''Called by worker. Setup g.user and g.db
        '''

        g.db = self.db_client[self.flsk_app.config['DB']]
        mongodb.authenticate(self.db_client)

        user_oid = kwargs.pop(self.USERID_ARG_NAME, None)

        if user_oid:
            db_user = g.db.users.find_one({'_id':ObjectId(user_oid)})
            login_user(user.User(
                db_user['user'],
                name=db_user['name'],
                _id=db_user['_id'],
                agency=db_user['agency'],
                admin=db_user['admin']))
            g.user = current_user

            print \
                '__call__: task=%s, g.user=%s, g.db=%s' %(
                self.name.split('.')[-1], g.user, type(g.db))
