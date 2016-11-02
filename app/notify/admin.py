
import logging
from bson import json_util
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

    if not user:
        return False

    return {
        'TEST_SERVER': True if os.environ['BRAVO_TEST_SERVER'] == 'True' else False,
        'SANDBOX_MODE': True if os.environ['BRAVO_SANDBOX_MODE'] == 'True' else False,
        'CELERY_BEAT': True if os.environ['BRAVO_CELERY_BEAT'] == 'True' else False,
        'ADMIN': user.get('admin'),
        'DEVELOPER': user.get('developer'),
        'USER_NAME': user['name']
    }

#-------------------------------------------------------------------------------
def update_agency_conf():
    user = db['users'].find_one({'user': current_user.username})

    logger.info('updating %s with value %s', request.form['field'], request.form['value'])

    '''old_value = db.agencies.find_one({'name':user['agency']})[request.form['field']]

    if type(old_value) != type(request.form['value']):
        logger.error('type mismatch')
        return False
    '''

    try:
        r = db.agencies.update_one(
            {'name':user['agency']},
            {'$set':{request.form['field']:request.form['value']}}
        )
    except Exception as e:
        logger.error(str(e))

    return True
