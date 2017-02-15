'''app.logger'''
from logging import Formatter, FileHandler, Filter, DEBUG, INFO, WARNING, ERROR
from config import LOG_PATH

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

#-------------------------------------------------------------------------------
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
