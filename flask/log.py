import mmap
import os

from config import *
from app import log_handler

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)

def get_tail(file, num_lines):
    size = os.path.getsize(LOG_FILE)

    with open(file, "rb") as f:
        fm = mmap.mmap(f.fileno(), 0, mmap.MAP_SHARED, mmap.PROT_READ)
        try:
            for i in xrange(size - 1, -1, -1):
                if fm[i] == '\n':
                    num_lines -= 1
                    if num_lines == -1:
                        break
                lines = fm[i + 1 if i else 0:].splitlines()
        except Exception as e:
            logger.error('/log: %s', str(e))
        finally:
            fm.close()

    return lines
