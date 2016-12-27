'''app.api.salesforce'''

import requests
import types
import re
from bson import json_util
import json
import logging
import pytz
from datetime import datetime
from simple_salesforce import Salesforce

from app import utils
from .. import db
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def get_help(sf):
    logger.info(help(sf))

#-------------------------------------------------------------------------------
def login():
    conf = db.agencies.find_one({'name':'vec'})

    sf = Salesforce(
        username=conf['salesforce']['username'],
        password=conf['salesforce']['password'],
        security_token=conf['salesforce']['security_token'])
        #sandbox=True)

    #logger.debug(utils.print_vars(sf, depth=0, l="    "))

    return sf

#-------------------------------------------------------------------------------
def add_contact(sf, obj):
    r = sf.Contact.create(obj)
    sf.Contact.update(r['id'],{'LastName': 'Jones', 'FirstName': 'John'})
    return r

#-------------------------------------------------------------------------------
def get_records(sf, block=None):
    '''Returns list of CampaignMembers dicts matching given Block. Related
    Contacts included under 'Contact' key.
    '''

    c_fields = []
    for field in dict(sf.Contact.describe())['fields']:
        c_fields.append('Contact.' + field['name'])

    cm_fields = []
    for field in dict(sf.CampaignMember.describe())['fields']:
        cm_fields.append(field['name'])

    try:
        response = sf.query(
            'SELECT ' + ', '.join(cm_fields) + ', ' + ', '.join(c_fields) + ' ' +\
            'FROM CampaignMember ' +\
            'WHERE Block__c includes ( \''+ block + '\')'
        )
    except Exception as e:
        logger.error('get_records fail: %s', str(e))
        return False

    if response['done'] != True:
        logger.error('still waiting for query')
        return False

    logger.debug('found %s records for %s', response['totalSize'], block)

    return response['records']

#-------------------------------------------------------------------------------
def add_block(sf, cm_obj, block):

    if block in cm_obj['Block__c']:
        logger.debug('obj already contains block %s', block)
        return False

    r = sf.CampaignMember.update(
        cm_obj['Id'],
        {"Block__c": cm_obj['Block__c'] + ';' + block}
    )

    if r != 204:
        logger.error('error removing %s', block)
    else:
        logger.debug('added %s onto CampaignMember Id %s', block, cm_obj['Id'])

    return r

#-------------------------------------------------------------------------------
def rmv_block(sf, cm_obj, block):
    blocks = cm_obj['Block__c'].split(';')
    new_list = [b for b in blocks if b != block]

    r = sf.CampaignMember.update(
        cm_obj['Id'],
        {'Block__c': ';'.join(new_list)}
    )

    if r != 204:
        logger.error('error removing %s', block)
    else:
        logger.debug('removed %s', block)

    return r
