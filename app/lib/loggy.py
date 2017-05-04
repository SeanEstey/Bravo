'''app.lib.loggy'''
import re
from logging import getLogger, Formatter, FileHandler, Filter, getLoggerClass
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
from datetime import datetime, timedelta
from config import LOG_PATH
from flask import g, session, has_app_context, has_request_context
from celery.utils.log import get_task_logger
from datetime import datetime
from app import db_client
from . import mongodb
from .utils import formatter

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

class DebugFilter(Filter):
    def filter(self, record):
        return record.levelno == 10
class InfoFilter(Filter):
    def filter(self, record):
        return record.levelno == 20
class WarningFilter(Filter):
    def filter(self, record):
        return record.levelno == 30


'''
Python logging notes

log.debug()
-level == 10
-logger invokes all attached handlers:
    dbg_hdlr->filter set to 10, returns True, msg logged to debug.log
    inf_hdlr->filter set to 20, returns False, nothing logged to events.log
    wrn_hdlr->filter set to 30, returns False, nothing logged to events.log
    ...
        parent_name = a_logger.parent.name if a_logger.parent else None
log.critical()
-level == 50
-logger invokes all attached handlers:
    dbg_hdlr->handles levels 10-10 w/ filter. Returns False, not logged
    wrn_hdlr->handlers levels 30-30 w/ filter. Returns False, not logged
    err_hdlr->no filter, handlers levels 40-50. msg is logged to events.log
'''


class Loggy():
    '''Each instance of this class contains a Logger object connected
    to a set of FileHandlers. Contains Logger wrapping functions which also
    save the log msg to the DB.
    '''

    #---------------------------------------------------------------------------
    @staticmethod
    def dump(a_logger, verbose=False):

        print 'logger name=%s, parent=%s, parent_name=%s, n_handlers=%s' %(
            a_logger.name, a_logger.parent, a_logger.parent.name, len(a_logger.handlers))

        if verbose:
            for hdlr in a_logger.handlers:
                print 'name=%s, type=%s, level=%s' %(
                    hdlr.name, type(hdlr), hdlr.level)

    #---------------------------------------------------------------------------
    @staticmethod
    def file_handler(level, filename, log_f=False, log_v=False):

        to_color = {
            '10': colors.WHITE,
            '20': colors.GRN,
            '30': colors.YLLW,
            '40': colors.RED,
            '50': colors.RED
        }

        handler = FileHandler(LOG_PATH + filename)
        handler.setLevel(level)

        if level == DEBUG: # 10
            handler.addFilter(DebugFilter())
        elif level == INFO: # 20
            handler.addFilter(InfoFilter())
        elif level == WARNING: # 30
            handler.addFilter(WarningFilter())

        if log_f:
            fmtr = Formatter(log_f, log_v)
        else:
            stamp_f = colors.BLUE + '[%(asctime)s %(name)s]: ' + colors.ENDC
            msg_f   = to_color[str(level)] + '%(message)s' + colors.ENDC
            fmtr = Formatter(stamp_f + msg_f, '%m-%d %H:%M')

        handler.setFormatter(fmtr)

        return handler

    #---------------------------------------------------------------------------
    @staticmethod
    def get_logs(start=None, end=None, user=None, groups=None, tag=None, levels=None):
        '''
        @start, end: naive datetime
        @show_levels: subset of ['debug', 'info', 'warning', 'error']
        @groups: subset of [g.user.agency, 'sys']
        '''

        DELTA_HRS = 24

        now = datetime.utcnow()
        start_dt = start if start else (now - timedelta(hours=DELTA_HRS))
        end_dt = end if end else now

        logs = g.db.logs.find({
            'tag':tag,
            'level': {'$in': levels} if levels else Loggy.levels,
            'user': user or {'$exists': True},
            'group': {'$in': groups} if groups else {'$exists':True},
            'created': {
               '$gte': start_dt,
               '$lt': end_dt}
            },
            {'_id':0}
        ).limit(50).sort('created', -1)

        print "%s logs queried" %(logs.count())

        return formatter(list(logs), bson_to_json=True)

    # Static Members
    regex_colors = re.compile('\\x1b\[[0-9]{1,2}m')
    levels = ['debug', 'info', 'warning', 'error']

    # Static Handlers
    dbg_hdlr = file_handler.__func__(DEBUG, 'debug.log')
    dbg_hdlr.name = 'loggy_dbg'
    inf_hdlr = file_handler.__func__(INFO, 'events.log')
    inf_hdlr.name = 'loggy_inf'
    wrn_hdlr = file_handler.__func__(WARNING, 'events.log')
    wrn_hdlr.name = 'loggy_wrn'
    err_hdlr = file_handler.__func__(ERROR, 'events.log')
    err_hdlr.name = 'loggy_err'

    # Instance Members
    logger = None
    name = None

    #---------------------------------------------------------------------------
    def _get_group(self, kwargs):
        '''one of ['wsf', 'vec', 'anon', 'sys']
        '''

        if kwargs.get('group'):
            return kwargs['group']
        elif has_app_context() and g.get('user'):
            return g.get('user').agency
        elif has_request_context() and session.get('agcy'):
            return session['agcy']
        else:
            return 'sys'

    #---------------------------------------------------------------------------
    def _get_user(self):
        '''user_id for
        '''

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

    #---------------------------------------------------------------------------
    def _insert(self, level, msg, args, kwargs):

        db = g.db if has_app_context() else db_client['bravo']

        frmt_msg = re.sub(Loggy.regex_colors, '', msg %(args))

        db.logs.insert_one({
            'msg': frmt_msg,
            'level': level,
            'name': self.name,
            'tag': kwargs.get('tag', None),
            'user': self._get_user(),
            'group': self._get_group(kwargs),
            'created': datetime.utcnow()
        })

    #---------------------------------------------------------------------------
    def debug(self, msg, *args, **kwargs):
        '''kwargs can include 'group', 'tag'
        '''

        #self._insert('debug', msg, args, kwargs)
        # Logger.debug only looks for kwargs 'exc_info' and 'extras'
        self.logger.debug(msg, *args)

    #---------------------------------------------------------------------------
    def info(self, msg, *args, **kwargs):

        self._insert('info', msg, args, kwargs)
        # Logger.info only looks for kwargs 'exc_info' and 'extras'
        self.logger.info(msg, *args)

    #---------------------------------------------------------------------------
    def warning(self, msg, *args, **kwargs):

        self._insert('warning', msg, args, kwargs)
        # Logger.warning only looks for kwargs 'exc_info' and 'extras'
        self.logger.warning(msg, *args)

    #---------------------------------------------------------------------------
    def error(self, msg, *args, **kwargs):

        self._insert('error', msg, args, kwargs)
        # Logger.error only looks for kwargs 'exc_info' and 'extras'
        self.logger.error(msg, *args)

    #---------------------------------------------------------------------------
    def exception(self, msg, *args, **kwargs):

        self._insert('error', msg, args, kwargs)
        # Logger.exception only looks for kwarg 'a'
        self.logger.exception(msg, *args)

    #---------------------------------------------------------------------------
    def __init__(self, name, celery_task=False):

        self.name = name
        self.logger = get_task_logger(name) if celery_task else getLogger(name)
        self.logger.addHandler(Loggy.dbg_hdlr)
        self.logger.addHandler(Loggy.inf_hdlr)
        self.logger.addHandler(Loggy.wrn_hdlr)
        self.logger.addHandler(Loggy.err_hdlr)
        self.logger.setLevel(DEBUG)
