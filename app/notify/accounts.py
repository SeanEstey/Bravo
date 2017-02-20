'''app.notify.accounts'''
import logging
from flask import g
from dateutil.parser import parse
from .. import get_logger, get_keys
from app.lib.dt import to_local
log = get_logger('notify.accts')

#-------------------------------------------------------------------------------
def add(agency, evnt_id, name, phone=None, email=None, udf=None, nameFormat=None):

    return g.db.accounts.insert_one({
        'evnt_id': evnt_id,
        'agency': agency,
        'name': name,
        'phone': phone,
        'email': email,
        'udf': udf,
        'nameFormat': nameFormat}).inserted_id

#-------------------------------------------------------------------------------
def edit_fields(acct_id, fields):
    '''User editing a notification value from GUI
    '''

    for fieldname, value in fields:
        if fieldname == 'udf.pickup_dt':
          try:
            value = to_local(parse(value))
          except Exception, e:
            log.error('Could not parse event_dt in /edit/call. %s', str(e))
            return 'Date edit failed. "%s" is not a valid date.' % value

        g.db.accounts.update({'_id':acct_id}, {'$set':{fieldname:value}})

        log.info('Editing ' + fieldname + ' to value: ' + str(value))

        return 'OK'
