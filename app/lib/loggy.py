'''app.lib.loggy'''
from logging import getLogger, Formatter, FileHandler, Filter
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
from config import LOG_PATH
from flask import g
from datetime import datetime

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

    # Static Members
    dbg_hdlr = file_handler.__func__(DEBUG, 'debug.log')
    inf_hdlr = file_handler.__func__(INFO, 'events.log')
    wrn_hdlr = file_handler.__func__(WARNING, 'events.log')
    err_hdlr = file_handler.__func__(ERROR, 'events.log')
    exc_hdlr = file_handler.__func__(CRITICAL, 'events.log')

    # Instance Member
    logger = None
    db = None

    #---------------------------------------------------------------------------
    def debug(self, msg, *args, **kwargs):

        agcy = kwargs['agcy'] if kwargs['agcy'] else g.user.agency
        self.db.logs.insert_one(
            {'agcy':agcy, 'lvl':'debug', 'msg':msg % (args), 'dt':datetime.now()})
        self.logger.debug(msg, *args)

    #---------------------------------------------------------------------------
    def info(self, msg, *args, **kwargs):

        agcy = kwargs['agcy'] if kwargs['agcy'] else g.user.agency
        self.db.logs.insert_one(
            {'agcy':agcy, 'lvl':'info', 'msg':msg % (args), 'dt':datetime.now()})
        self.logger.info(msg, *args)

    #---------------------------------------------------------------------------
    def warning(self, msg, *args, **kwargs):

        agcy = kwargs['agcy'] if kwargs['agcy'] else g.user.agency
        self.db.logs.insert_one(
            {'agcy':agcy, 'lvl':'task', 'msg':msg % (args), 'dt':datetime.now()})
        self.logger.warning(msg, *args)

    #---------------------------------------------------------------------------
    def error(self, msg, *args, **kwargs):

        agcy = kwargs['agcy'] if kwargs['agcy'] else g.user.agency
        self.db.logs.insert_one(
            {'agcy':agcy, 'lvl':'error', 'msg':msg % (args), 'dt':datetime.now()})
        self.logger.error(msg, *args)

    #---------------------------------------------------------------------------
    def critical(self, msg, *args, **kwargs):
        pass

    #---------------------------------------------------------------------------
    def __init__(self, name, db):

        self.db = db
        self.logger = getLogger(name)
        self.logger.addHandler(Loggy.dbg_hdlr)
        self.logger.addHandler(Loggy.inf_hdlr)
        self.logger.addHandler(Loggy.wrn_hdlr)
        self.logger.addHandler(Loggy.err_hdlr)
        self.logger.addHandler(Loggy.exc_hdlr)
        self.logger.setLevel(DEBUG)
