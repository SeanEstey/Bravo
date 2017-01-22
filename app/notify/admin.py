import logging, os
from bson import json_util
from flask import g, request
from flask_login import current_user
from .. import get_keys
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def auth_request_type(_type):
    '''Check if request is from client. If so, verify they
    have permission'''

    origin_ip = request.environ.get('HTTP_X_REAL_IP')

    if origin_ip and origin_ip == os.environ['BRAVO_HTTP_HOST']:
        return True

    # Request is from client

    if _type == 'admin':
        if g.user.admin:
            log.info('client "%s" request authorized', _type)
            return True
    elif _type == 'developer':
        if g.user.developer:
            log.info('client "%s" request authorized', _type)
            return True

    log.error('client "%s" request denied', _type)

    return False

#-------------------------------------------------------------------------------
def get_op_stats():
    #if not g.user:
    #    return False

    return {
        'TEST_SERVER': True if os.environ['BRAVO_TEST_SERVER'] == 'True' else False,
        'SANDBOX_MODE': True if os.environ['BRAVO_SANDBOX_MODE'] == 'True' else False,
        'CELERY_BEAT': True if os.environ['BRAVO_CELERY_BEAT'] == 'True' else False,
        'ADMIN': g.user.admin,
        'DEVELOPER': g.user.developer,
        'USER_NAME': g.user.name
    }

#-------------------------------------------------------------------------------
def update_agency_conf():
    log.info('updating %s with value %s', request.form['field'], request.form['value'])

    '''old_value = db.agencies.find_one({'name':user['agency']})[request.form['field']]

    if type(old_value) != type(request.form['value']):
        log.error('type mismatch')
        return False
    '''

    try:
        r = g.db.agencies.update_one(
            {'name':g.user.agency},
            {'$set':{request.form['field']:request.form['value']}}
        )
    except Exception as e:
        log.error(str(e))

    return True
