'''app.notify.admin'''
import os
from bson import json_util
from flask import g, request
from .. import get_keys
from app.lib.loggy import Loggy
log = Loggy('notify.admin')

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
