import mmap
import logging
import os

from config import *
from app import info_handler, error_handler

logger = logging.getLogger(__name__)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)

def get_tail(file_path, num_lines):
    try:
        size = os.path.getsize(file_path)
    except Exception as e:
        logger.error('%s does not exist!', file_path)
        return []

    if size == 0:
        return []

    lines = []

    try:
        with open(file_path, "rb") as f:
            fm = mmap.mmap(f.fileno(), 0, mmap.MAP_SHARED, mmap.PROT_READ)

            for i in xrange(size - 1, -1, -1):
                if fm[i] == '\n':
                    num_lines -= 1
                    if num_lines == -1:
                        break
                lines = fm[i + 1 if i else 0:].splitlines()

            fm.close()
    except Exception as e:
        logger.error('/log: %s', str(e))

    return lines
