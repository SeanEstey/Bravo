import logging, sys, pymongo
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
import datetime as dt
from pymongo.collection import Collection
from pymongo.errors import OperationFailure, PyMongoError
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
write_method = 'insert_one'
write_many_method = 'insert_many'
_connection = None
g = {}

def has_app_context():
    return True

def has_request_context():
    return True

#-------------------------------------------------------------------------------
class MongoFormatter(logging.Formatter):

    DEFAULT_PROPERTIES = logging.LogRecord(
        '', '', '', '', '', '', '', '').__dict__.keys()

    def _get_group(self):
        global g

        if g.get('group'):
            return g.get('group')
        else:
            return 'sys'

    def _get_user(self):
        global g

        # Bravo user
        if has_app_context() and g.get('user'):
            return g.get('user')#.user_id
        elif has_request_context():
            return 'session_user'
            '''# Reg. end-user using Alice
            if session.get('account'):
                return session['account']['id']
            # Unreg. end-user using Alice
            elif session.get('anon_id'):
                return session['anon_id']
            # Celery task w/ req ctx
            else:
                return 'sys'
            '''
        # System task
        else:
            return 'sys'

    def format(self, record):
        """Formats LogRecord into python dictionary."""
        # Standard document
        document = {
            'group': self._get_group(),
            'user': self._get_user(),
            'timestamp': dt.datetime.utcnow(),
            'level': record.levelname,
            'message': record.getMessage(),
            'loggerName': record.name
            #'thread': record.thread,
            #'threadName': record.threadName,
            #'fileName': record.pathname,
            #'module': record.module,
            #'method': record.funcName,
            #'lineNumber': record.lineno
        }
        # Standard document decorated with exception info
        if record.exc_info is not None:
            document.update({
                'exception': {
                    'message': str(record.exc_info[1]),
                    'code': 0,
                    'stackTrace': self.formatException(record.exc_info)
                }
            })
        # Standard document decorated with extra contextual information
        if len(self.DEFAULT_PROPERTIES) != len(record.__dict__):
            contextual_extra = set(record.__dict__).difference(
                set(self.DEFAULT_PROPERTIES))
            if contextual_extra:
                for key in contextual_extra:
                    document[key] = record.__dict__[key]
        return document

#-------------------------------------------------------------------------------
class MongoHandler(logging.Handler):

    def __init__(self, level=INFO, formatter=None, fail_silently=False, reuse=True,
                 host='localhost', port=27017, db_name=None, coll='logs',
                 auth_db_name='admin', user=None, pw=None,
                 capped=False, cap_max=1000, cap_size=1000000, **kwargs):
        '''Init Mongo DB connection.
        @reuse: if False, every handler will have it's own MongoClient (slow).
        '''

        logging.Handler.__init__(self, level)
        self.host = host
        self.port = port
        self.db_name = db_name
        self.coll_name = coll
        self.user = user
        self.pw = pw
        self.auth_db_name = auth_db_name
        self.fail_silently = fail_silently
        self.connection = None
        self.db = None
        self.coll = None
        self.authenticated = False
        self.formatter = formatter or MongoFormatter()
        self.capped = capped
        self.cap_max = cap_max
        self.cap_size = cap_size
        self.reuse = reuse
        self._connect(**kwargs)

    def _connect(self, **kwargs):
        global _connection

        if self.reuse and _connection:
            self.connection = _connection
        else:
            self.connection = MongoClient(host=self.host, port=self.port, **kwargs)
            _connection = self.connection

        self.db = self.connection[self.db_name]

        if self.user is not None and self.pw is not None:
            auth_db = self.connection[self.auth_db_name]
            self.authenticated = auth_db.authenticate(self.user, self.pw, mechanism='SCRAM-SHA-1')

        try:
            self.connection.admin.command('ismaster')
        except ConnectionFailure:
            if self.fail_silently:
                return
            else:
                raise

        if self.capped:
            # Prevent override of capped collection
            try:
                self.coll = Collection(self.db, self.coll_name,
                                             capped=True, max=self.cap_max,
                                             size=self.cap_size)
            except OperationFailure:
                # Capped collection exists, so get it.
                self.coll = self.db[self.coll_name]
        else:
            self.coll = self.db[self.coll_name]

    def close(self):
        '''If authenticated, logging out and closing mongo database connection.
        '''
        if self.authenticated:
            self.db.logout()
        if self.connection is not None:
            self.connection.close()

    def emit(self, record):
        '''Inserting new logging record to mongo database.
        '''
        if self.coll is not None:
            try:
                getattr(self.coll, write_method)(self.format(record))
            except Exception:
                if not self.fail_silently:
                    self.handleError(record)

    def __exit__(self, type, value, traceback):
        self.close()

#-------------------------------------------------------------------------------
class BufferedMongoHandler(MongoHandler):
    '''Provides buffering mechanism to avoid write-locking mongo.'''

    def __init__(self, level=INFO, formatter=None, fail_silently=False, reuse=True,
                 host='localhost', port=27017, db_name=None, coll='logs',
                 auth_db_name='admin', user=None, pw=None,
                 capped=False, cap_max=1000, cap_size=1000000,
                 buf_size=100, buf_flush_tim=5.0, buf_flush_lvl=CRITICAL, **kwargs):
        '''@buf_flush_tim: freq. that buffer saved to Mongo. None/0 prevent
        flush until full buf or critical message sent.'''

        MongoHandler.__init__(self,
            level=level, formatter=formatter, fail_silently=fail_silently, reuse=reuse,
            host=host, port=port, db_name=db_name, coll=coll, user=user, pw=pw, auth_db_name=auth_db_name,
            capped=capped, cap_max=cap_max, cap_size=cap_size, **kwargs)

        self.buf = []
        self.buf_size = buf_size
        self.buf_flush_tim = buf_flush_tim
        self.buf_flush_lvl = buf_flush_lvl
        self.last_record = None # kept for handling the error on flush
        self.buf_timer_thread = None
        self._buf_lock = None
        self._timer_stopper = None

        if self.buf_flush_tim:
            # clean exit event
            import atexit
            atexit.register(self.destroy)

            # retrieving main thread as a safety
            import threading
            main_thead = threading.current_thread()
            self._buf_lock = threading.RLock()

            # call at interval function
            def call_repeatedly(interval, func, *args):
                stopped = threading.Event()

                # actual thread function
                def loop():
                    while not stopped.wait(interval) and main_thead.is_alive():  # the first call is in `interval` secs
                        func(*args)

                timer_thread = threading.Thread(target=loop)
                timer_thread.daemon = True
                timer_thread.start()
                return stopped.set, timer_thread

            # launch thread
            self._timer_stopper, self.buf_timer_thread = call_repeatedly(self.buf_flush_tim, self.flush_to_mongo)

    def emit(self, record):
        """Inserting new logging record to buffer and flush if necessary."""
        self.add_to_buf(record)

        if len(self.buf) >= self.buf_size or record.levelno >= self.buf_flush_lvl:
            self.flush_to_mongo()
        return

    def buf_lock_acquire(self):
        """Acquire lock on buffer (only if periodical flush is set)."""
        if self._buf_lock:
            self._buf_lock.acquire()

    def buf_lock_release(self):
        """Release lock on buffer (only if periodical flush is set)."""
        if self._buf_lock:
            self._buf_lock.release()

    def add_to_buf(self, record):
        """Add a formatted record to buffer."""
        self.buf_lock_acquire()
        self.last_record = record
        self.buf.append(self.format(record))
        self.buf_lock_release()

    def flush_to_mongo(self):
        """Flush all records to mongo database."""
        if self.coll is not None and len(self.buf) > 0:
            print 'flushing to mongo'
            self.buf_lock_acquire()
            try:

                getattr(self.coll, write_many_method)(self.buf)
                self.empty_buf()

            except Exception as e:
                if not self.fail_silently:
                    self.handleError(self.last_record) #handling the error on flush
            finally:
                self.buf_lock_release()

    def empty_buf(self):
        """Empty the buffer list."""
        del self.buf
        self.buf = []

    def destroy(self):
        """Clean quit logging. Flush buffer. Stop the periodical thread if needed."""
        if self._timer_stopper:
            self._timer_stopper()
        self.flush_to_mongo()
        self.close()
