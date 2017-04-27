'''app.lib.loggy'''
from logging import getLogger, Formatter, FileHandler, Filter
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
from datetime import datetime, timedelta
from config import LOG_PATH
from flask import g
from celery.utils.log import get_task_logger
from datetime import datetime
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


class Loggy():
    '''Each instance of this class contains a Logger object connected
    to a set of FileHandlers. Contains Logger wrapping functions which also
    save the log msg to the DB.
    '''

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
    def get_logs(start=None, end=None, user=None, group=None, tag=None, levels=None):
        '''
        @start, end: naive datetime
        @show_levels: list of subset ['debug', 'info', 'warning', 'error']
        '''

        logs = g.db.logs.find(
            {'tag':tag,
             'level': {'$in': levels or Loggy.levels},
             'user': user or {'$exists': True},
             'group': group or {'$exists': True},
             'created': {
                '$gte': start or (datetime.utcnow() - timedelta(hours=24)),
                '$lt': end or datetime.utcnow()
             },
            },
            {'_id':0}
        ).limit(25).sort('created', -1)

        print "found %s logs" %(logs.count())

        return formatter(list(logs), bson_to_json=True) #, to_json=True)

    # Static Members
    levels = ['debug', 'info', 'warning', 'error']
    dbg_hdlr = file_handler.__func__(DEBUG, 'debug.log')
    inf_hdlr = file_handler.__func__(INFO, 'events.log')
    wrn_hdlr = file_handler.__func__(WARNING, 'events.log')
    err_hdlr = file_handler.__func__(ERROR, 'events.log')
    exc_hdlr = file_handler.__func__(CRITICAL, 'events.log')

    # Instance Members
    logger = None
    name = None

    #---------------------------------------------------------------------------
    def _get_group(self, kwargs):
        '''one of ['wsf', 'vec', 'anon', 'sys']
        '''

        if kwargs.get('group'):
            return kwargs['group']
        elif g.get('user'):
            return g.get('user').agency
        else:
            return 'sys'

    #---------------------------------------------------------------------------
    def _get_user(self):
        '''user_id for
        '''

        if g.get('user'):
            return g.get('user').user_id
        else:
            return 'sys'

    #---------------------------------------------------------------------------
    def _insert(self, level, msg, args, kwargs):

        g.db.logs.insert_one({
            'msg': msg %(args),
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

        self._insert('debug', msg, args, kwargs)
        self.logger.debug(msg, *args)

    #---------------------------------------------------------------------------
    def info(self, msg, *args, **kwargs):

        self._insert('info', msg, args, kwargs)
        self.logger.info(msg, *args)

    #---------------------------------------------------------------------------
    def warning(self, msg, *args, **kwargs):

        self._insert('warning', msg, args, kwargs)
        self.logger.warning(msg, *args)

    #---------------------------------------------------------------------------
    def error(self, msg, *args, **kwargs):

        self._insert('error', msg, args, kwargs)
        self.logger.error(msg, *args)

    #---------------------------------------------------------------------------
    def critical(self, msg, *args, **kwargs):

        pass

    #---------------------------------------------------------------------------
    def __init__(self, name, celery_task=False):

        self.name = name
        self.logger = get_task_logger(name) if celery_task else getLogger(name)
        self.logger.addHandler(Loggy.dbg_hdlr)
        self.logger.addHandler(Loggy.inf_hdlr)
        self.logger.addHandler(Loggy.wrn_hdlr)
        self.logger.addHandler(Loggy.err_hdlr)
        self.logger.addHandler(Loggy.exc_hdlr)
        self.logger.setLevel(DEBUG)
