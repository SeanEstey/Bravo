'''app.logger'''
import logging
from config import LOG_PATH
from .utils import bcolors

#-------------------------------------------------------------------------------
def create_file_handler(level, filename):
    class DebugFilter(logging.Filter):
        def filter(self, record):
            return record.levelno == 10
    class InfoFilter(logging.Filter):
        def filter(self, record):
            return record.levelno == 20

    handler = logging.FileHandler(LOG_PATH + filename)
    handler.setLevel(level)

    stamp_frmt = bcolors.OKBLUE + '[%(asctime)s %(name)s]: ' + bcolors.ENDC
    msg_frmt = '%(message)s'

    if level == logging.DEBUG:
        stamp_frmt += bcolors.WARNING
        msg_frmt += bcolors.ENDC
        handler.addFilter(DebugFilter())
    elif level == logging.INFO:
        stamp_frmt += bcolors.OKGREEN
        msg_frmt += bcolors.ENDC
        handler.addFilter(InfoFilter())
    elif level == logging.ERROR:
        stamp_frmt += bcolors.FAIL
        msg_frmt += bcolors.ENDC

    handler.setFormatter(logging.Formatter(stamp_frmt+msg_frmt, '%m-%d %H:%M'))

    return handler
