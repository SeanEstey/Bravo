'''app.main.agency'''

import logging
from flask import g, request
from app import get_logger, get_keys
log = get_logger('etap')

#-------------------------------------------------------------------------------
def get_conf():
    return get_keys()

#-------------------------------------------------------------------------------
def update_conf(data=None):
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
