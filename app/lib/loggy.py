'''app.lib.loggy'''
from logging import getLogger, Formatter, FileHandler, Filter, DEBUG, INFO, WARNING, ERROR
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

    # Static FileHandlers
    dbg_hdlr = file_handler(DEBUG, 'debug.log') # May not work calling method defined inside own class
    inf_hdlr = file_handler(INFO, 'events.log')
    wrn_hdlr = file_handler(WARNING, 'events.log')
    err_hdlr = file_handler(ERROR, 'events.log')
    exc_hdlr = file_handler(CRITICAL, 'events.log')
    # Instance logger
    logger = None

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
    def debug(self, msg, *args):

        g.db.logs.insert_one(
            {'agcy':g.user.agency, 'lvl':'debug', 'msg':msg % (args), 'dt':datetime.now()})
        logger.debug(msg, *args)

    #---------------------------------------------------------------------------
    def info(self, msg, *args):

        g.db.logs.insert_one(
            {'agcy':g.user.agency, 'lvl':'info', 'msg':msg % (args), 'dt':datetime.now()})
        logger.info(msg, *args)

    #---------------------------------------------------------------------------
    def task(self, msg, *args):

        g.db.logs.insert_one(
            {'agcy':g.user.agency, 'lvl':'task', 'msg':msg % (args), 'dt':datetime.now()})
        logger.warning(msg, *args)

    #---------------------------------------------------------------------------
    def error(self, msg, *args):

        g.db.logs.insert_one(
            {'agcy':g.user.agency, 'lvl':'error', 'msg':msg % (args), 'dt':datetime.now()})
        logger.error(msg, *args)

    #---------------------------------------------------------------------------
    def __init__(self, name):

        self.logger = getLogger(name)
        self.logger.addHandler(dbg_hdlr)
        self.logger.addHandler(inf_hdlr)
        self.logger.addHandler(wrn_hdlr)
        self.logger.addHandler(err_hdlr)
        self.logger.addHandler(exc_hdlr)
        self.logger.setLevel(DEBUG)
