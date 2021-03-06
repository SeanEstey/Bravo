import logging
import traceback
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
from datetime import datetime
from flask import g, has_app_context
from pymongo.collection import Collection
from pymongo.errors import OperationFailure, PyMongoError, ConnectionFailure
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from config import LOG_PATH
from app import get_username, get_group
write_method = 'insert_one'
write_many_method = 'insert_many'
_connection = None

#-------------------------------------------------------------------------------
class MongoFormatter(logging.Formatter):
    '''Based on log4mongo in PyPI'''

    DEFAULT_PROPERTIES = logging.LogRecord(
        '', '', '', '', '', '', '', '').__dict__.keys()

    def format(self, record):
        """Formats LogRecord into python dictionary."""

        # Standard document
        document = {
            'extra': {},
            'standard': {
                'timestamp': datetime.utcnow(),
                'level': record.levelname,
                'message': record.getMessage(),
                'process': record.process,
                'processName': record.processName,
                'loggerName': record.name,
                'thread': record.thread,
                'threadName': record.threadName,
                'fileName': record.pathname,
                'module': record.module,
                'method': record.funcName,
                'lineNumber': record.lineno
            }
        }

        # Standard document decorated with exception info
        if record.exc_info is not None:
            document['standard'].update({
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
                    if key == 'asctime' or key == 'message':
                        continue
                    document['extra'][key] = record.__dict__[key]

        # More Flask context in g
        if has_app_context():
            document['standard']['group'] = get_group()
            document['standard']['user'] = get_username()

            if g.get('timer'):
                document['standard']['elapsed'] = g.timer.clock(t='ms',stop=False)

            if g.get('tag'):
                document['standard']['tag'] = g.tag

        return document

#-------------------------------------------------------------------------------
class MongoHandler(logging.Handler):
    '''Based on log4mongo in PyPI'''

    def __init__(self, level=INFO, formatter=None, raise_exc=True, reuse=True,
                 client=None, host='localhost', port=27017, connect=False, db_name=None, coll='logs',
                 auth_db_name='admin', user=None, pw=None,
                 capped=False, cap_max=1000, cap_size=1000000, **kwargs):
        '''Init Mongo DB connection.
        @reuse: if False, every handler will have it's own MongoClient (slow).
        @kwargs: list of keywords to pass to _connect()
        @connect: if False, defer creating MongoClient and connection until
        required (for forked celery tasks)'''

        logging.Handler.__init__(self, level)
        global _connection
        _connection = client
        self.conn = None
        self.db = None
        self.coll = None
        self.is_authed = False
        self.host = host
        self.port = port
        self.raise_exc = raise_exc
        self.reuse = reuse
        self.db_name = db_name
        self.coll_name = coll
        self.auth_db_name = auth_db_name
        self.user = user
        self.pw = pw
        self.formatter = formatter or MongoFormatter()
        self.capped = capped
        self.cap_max = cap_max
        self.cap_size = cap_size
        self.kwargs = kwargs

        if connect:
            self._connect(**self.kwargs)

    def test_connection(self):
        if not self.conn:
            return False
        try:
            self.conn.admin.command('ismaster')
        except ConnectionFailure:
            print 'No mongo connection!'
            raise
            #return False
        else:
            return True

    def _connect(self, **kwargs):
        global _connection

        if self.reuse and _connection:
            self.conn = _connection
        else:
            raise Exception('No connection available!')

        self.test_connection()

        self.db = self.conn[self.db_name]

        if self.user is not None and self.pw is not None:
            auth_db = self.conn[self.auth_db_name]

            self.is_authed = auth_db.authenticate(
                self.user,
                self.pw,
                mechanism='SCRAM-SHA-1')

        if self.capped:
            # Prevent override of capped collection
            try:
                self.coll = Collection(
                    self.db, self.coll_name,
                    capped=True, max=self.cap_max, size=self.cap_size)
            except OperationFailure:
                # Capped collection exists, so get it.
                self.coll = self.db[self.coll_name]
        else:
            self.coll = self.db[self.coll_name]

    def close(self):
        '''If authenticated, logging out and closing mongo database connection.
        '''
        if self.is_authed:
            self.db.logout()
        if self.conn is not None:
            self.conn.close()

    def emit(self, record):
        '''Inserting new logging record to mongo database.
        '''
        if self.conn is None:
            self._connect(**self.kwargs)

        if self.coll is not None:
            try:
                getattr(self.coll, write_method)(self.format(record))
            except Exception:
                if not self.raise_exc:
                    self.handleError(record)

    def __exit__(self, type, value, traceback):
        self.close()

#-------------------------------------------------------------------------------
class BufferedMongoHandler(MongoHandler):
    '''Based on log4mongo in PyPI
    Provides buffering mechanism to avoid write-locking mongo.'''

    def __init__(self, level=INFO, formatter=None, raise_exc=True, reuse=True,
                 host='localhost', port=27017, connect=False, db_name=None, coll='logs',
                 auth_db_name='admin', user=None, pw=None,
                 capped=True, cap_max=10000, cap_size=10000000,
                 buf_size=50, buf_flush_tim=5.0, buf_flush_lvl=ERROR, **kwargs):
        '''@buf_flush_tim: freq. that buffer saved to Mongo. None/0 prevent
        flush until full buf or critical message sent.'''

        MongoHandler.__init__(self,
            level=level, formatter=formatter, raise_exc=raise_exc, reuse=reuse,
            host=host, port=port, connect=connect, db_name=db_name, coll=coll, user=user, pw=pw, auth_db_name=auth_db_name,
            capped=capped, cap_max=cap_max, cap_size=cap_size, **kwargs)

        self.buf = []
        self.buf_size = buf_size
        self.buf_flush_tim = buf_flush_tim
        self.buf_flush_lvl = buf_flush_lvl
        self.last_record = None # kept for handling the error on flush
        self.buf_timer_thread = None
        self._buf_lock = None
        self._timer_stopper = None

        #if self.buf_flush_tim:
        #    self.init_buf_timer()

    def init_buf_timer(self):
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

        if self.conn is None:
            self._connect(**self.kwargs)

        if self.coll is not None and len(self.buf) > 0:
            self.buf_lock_acquire()

            try:
                getattr(self.coll, write_many_method)(self.buf)
                self.empty_buf()
            except Exception as e:
                from bson.json_util import dumps
                print 'Mongo error: %s. Buf: %s'%(
                    e.message, len(self.buf), dumps(self.buf))

                self.empty_buf()

                if not self.raise_exc:
                    self.handleError(self.last_record)
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
