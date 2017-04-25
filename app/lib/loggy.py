
import logging
from datetime import datetime
from app import get_logger

class Loggy():

    logger = None

    def debug(self, msg, *args):
        full_msg = ''
        # Save to db
        g.db.logs.insert_one(
            {'agcy':g.user.agency, 'msg':full_msg, 'dt':datetime.now()})
        logger.debug(msg, *args)

    def info(self, msg, *args):
        # save to db
        logger.info(msg, *args)

    def task(self, msg, *args):
        # save to db
        logger.warning(msg, *args)

    def error(self, msg, *args):
        # save to db
        logger.error(msg, *args)

    def __init__(self, name):
        self.logger = get_logger(name)
