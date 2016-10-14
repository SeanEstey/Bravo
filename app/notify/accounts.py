'''app.notify.accounts'''

import logging
from dateutil.parser import parse
from .. import db
logger = logging.getLogger(__name__)

# TODO: rename all refs to 'id' field to 'etap_id'

#-------------------------------------------------------------------------------
def add(agency, a_id, name, phone=None, email=None, udf=None):
    return db['accounts'].insert_one({
        'name': name,
        'id': a_id,
        'phone': phone,
        'email': email,
        'udf': udf
    }).inserted_id

#-------------------------------------------------------------------------------
def edit(acct_id, fields):
    '''User editing a notification value from GUI
    '''
    for fieldname, value in fields:
        if fieldname == 'udf.pickup_dt':
          try:
            value = parse(value)
          except Exception, e:
            logger.error('Could not parse event_dt in /edit/call')
            return '400'

        db['accounts'].update({'_id':acct_id}, {'$set':{fieldname:value}})

        # update notification 'to' fields if phone/email edited
        if fieldname == 'email':
            db['notifics'].update_one(
                {'acct_id':acct_id},
                {'$set':{'to':value}})
        elif fieldname == 'phone':
            db['notifics'].update_one(
                {'acct_id':acct_id, '$or': [{'type':'voice'},{'type':'sms'}]},
                {'$set': {'to':value}})

        logger.info('Editing ' + fieldname + ' to value: ' + str(value))

        return True
