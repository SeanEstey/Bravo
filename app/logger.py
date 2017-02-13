'''app.logger'''
import logging
from logging import Formatter, FileHandler, Filter, DEBUG, INFO, WARNING, ERROR
from config import LOG_PATH
from app.utils import bcolors as c

class DebugFilter(Filter):
    def filter(self, record):
        return record.levelno == 10
class InfoFilter(Filter):
    def filter(self, record):
        return record.levelno == 20
class WarningFilter(Filter):
    def filter(self, record):
        return record.levelno == 30

#-------------------------------------------------------------------------------
def file_handler(level, filename, log_f=False, log_v=False):

    colors = {
        '10': c.WHITE,
        '20': c.OKGREEN,
        '30': c.WARNING,
        '40': c.FAIL,
        '50': c.FAIL
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
        stamp_f = c.OKBLUE + '[%(asctime)s %(name)s]: ' + c.ENDC
        msg_f   = colors[str(level)] + '%(message)s' + c.ENDC
        fmtr = Formatter(stamp_f + msg_f, '%m-%d %H:%M')

    handler.setFormatter(fmtr)

    return handler
