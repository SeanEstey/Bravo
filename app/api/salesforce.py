'''app.api.salesforce'''

import base64
import types
import re
from bson import json_util
import json
import logging
import pytz
from datetime import datetime
from simple_salesforce import Salesforce

from app import utils
from .. import get_db
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def login(sandbox=False):
    '''Make sure to keep simple_salesforce pkg and 'version' arg up to date
    '''

    conf = db.agencies.find_one({'name':'vec'})

    username=conf['salesforce']['username']

    if sandbox:
        username += '.vecova'

    sf = Salesforce(
        username=username,
        password=conf['salesforce']['password'],
        security_token=conf['salesforce']['security_token'],
        version='38.0',
        sandbox=sandbox)

    logger.debug(
        'login successful. user="%s" api="v%s"',
        conf['salesforce']['username'], sf.sf_version)

    return sf

#-------------------------------------------------------------------------------
def add_account(sf, contact, block, status, neighborhood, next_pickup):
    try:
        c_resp = sf.Contact.create(contact)
    except Exception as e:
        logger.error(str(e))
        return False

    try:
        q_resp = sf.query(
            "SELECT Id FROM Campaign WHERE Name = 'Bottle Service'")
    except Exception as e:
        logger.error(str(e))

    try:
        cm_resp = sf.CampaignMember.create({
            'CampaignId': q_resp['records'][0]['Id'],
            'ContactId': c_resp['id'],
            'Block__c': block,
            'Status': status,
            'Neighborhood__c': neighborhood,
            'Next_Pickup__c': next_pickup
        })
    except Exception as e:
        logger.error(str(e))
        return False

    if cm_resp['success'] == True:
        logger.debug(
            'account created successfully. name="%s %s" id="%s"',
            contact['FirstName'], contact['LastName'], c_resp['id'])

    return c_resp['id']

#-------------------------------------------------------------------------------
def add_gift(sf, a_id, campaign_id, amount, date, note):
    '''date: gift date (yyyy-mm-dd)'''

    try:
        r = sf.Opportunity.create({
            'AccountId': a_id,
            'CampaignId': campaign_id,
            'Name': 'Bottle Donation',
            'Amount': amount,
            'StageName': 'In-Kind Received',
            'CloseDate': date,
            'Description': note
        })
    except Exception as e:
        logger.error('error creating gift for %s: "%s"', a_id, str(e))
        return False

    #logger.debug(r)

    return True

#-------------------------------------------------------------------------------
def add_note(sf, c_id, title, note):
    '''Add note related to Contact record'''

    try:
        note = sf.ContentNote.create({
            'Content': base64.b64encode(note),
            'Title': title,
            'OwnerId': c_id
        })

        link = sf.ContentDocumentLink.create({
            'ContentDocumentId': note['id'],
            'LinkedEntityId': c_id,
            'ShareType': 'V'

        })
    except Exception as e:
        logger.error('error creating note for c_id %s: "%s"', c_id, str(e))
        return False

    return True

#-------------------------------------------------------------------------------
def match_records(sf, block=None, address=None, name=None):
    '''Returns list of CampaignMember obj including 'Contact' relationship
    fields, matching given criteria.
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
def search_records(sf, term):
    '''More general search than match_records using SOSL'''

    #FIND {Joe Smith} IN Name Fields RETURNING lead(name, phone)

    return True

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
