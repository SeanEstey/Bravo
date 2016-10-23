
import logging
import os
from flask import request
from flask_login import current_user

from .. import db
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def auth_request_type(_type):
    '''Check if request is from client. If so, verify they
    have permission'''

    origin_ip = request.environ.get('HTTP_X_REAL_IP')

    if origin_ip and origin_ip == os.environ['BRAVO_HTTP_HOST']:
        return True

    # Request is from client

    user = db['users'].find_one({'user': current_user.username})

    if _type == 'admin':
        if user['admin']:
            logger.info('client "%s" request authorized', _type)
            return True
    elif _type == 'developer':
        if user['developer']:
            logger.info('client "%s" request authorized', _type)
            return True

    logger.error('client "%s" request denied', _type)

    return False

#-------------------------------------------------------------------------------
def get_op_stats():
    user = db['users'].find_one({'user': current_user.username})

    logger.info(user)

    if not user:
        return False

    return {
        'TEST_SERVER': bool(os.environ['BRAVO_TEST_SERVER']),
        'SANDBOX_MODE': bool(os.environ['BRAVO_SANDBOX_MODE']),
        'CELERY_BEAT': bool(os.environ['BRAVO_CELERY_BEAT']),
        'ADMIN': user['admin'],
        'DEVELOPER': user['developer'],
        'USER_NAME': user['name']
    }
