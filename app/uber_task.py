    __all__ = ['RequestContextTask']

    class RequestContextTask(Task):
        CONTEXT_ARG_NAME = '_flask_request_context'
        USER_ID_OID_ARG_NAME = '_user_id_oid'

        def __call__(self, *args, **kwargs):
            '''Called by worker'''

            print '__call__'
            req_ctx = has_request_context()
            app_ctx = has_app_context()
            call = lambda: super(RequestContextTask, self).__call__(*args, **kwargs)
            context = kwargs.pop(self.CONTEXT_ARG_NAME, None)

            if context is None or req_ctx:
                if not app_ctx:
                    with app.app_context():
                        self._push_globals(kwargs)
                        return call()
                else:
                    self._push_globals(kwargs)
                    return call()

            with app.test_request_context(**context):
                self._push_globals(kwargs)
                result = call()
                app.process_response(make_response(result or ''))

            return result

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

        def async(self, args=None, kwargs=None, task_id=None, producer=None,
            link=None, link_error=None, shadow=None, **options):
            '''Called by Flask app'''

            if options.pop('with_request_context', True):
                self._include_request_context(kwargs)
            if has_app_context():
                kwargs[self.USER_ID_OID_ARG_NAME] = str(g.user._id)
            options['queue'] = 'bravo'
            return super(RequestContextTask, self).apply_async(args, kwargs, task_id, producer,
                link, link_error, shadow, **options)

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

        def _push_globals(self, kwargs):
            '''Called by worker'''
            g.db = task_db_client['bravo']
            mongodb.authenticate(task_db_client)

            user_id_oid = kwargs.pop(self.USER_ID_OID_ARG_NAME, None)

            if user_id_oid:
                db_user = g.db.users.find_one({'_id':ObjectId(user_id_oid)})
                login_user(user.User(
                    db_user['user'],
                    name=db_user['name'],
                    _id=db_user['_id'],
                    agency=db_user['agency'],
                    admin=db_user['admin']))
                g.user = current_user

                print 'loaded user=%s into g.user' % g.user

