'''app.main.agency'''
from flask import g, request, current_app
from app import get_keys
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def get_conf():
    return get_keys()

#-------------------------------------------------------------------------------
def update_conf(data=None):
    log.info('updating %s with value %s', request.form['field'], request.form['value'])

    '''old_value = g.db['groups'].find_one({'name':user['agency']})[request.form['field']]

    if type(old_value) != type(request.form['value']):
        log.error('type mismatch')
        return False
    '''

    try:
        r = g.db['groups'].update_one(
            {'name':g.group},
            {'$set':{request.form['field']:request.form['value']}}
        )
    except Exception as e:
        log.error(str(e))

    return True
