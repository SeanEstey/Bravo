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
def get_contact(sf, c_id):
    contact = sf.Contact.get(c_id)
    return contact

#-------------------------------------------------------------------------------
def print_contact(sf, c_id):
    contact = sf.Contact.get(c_id)
    logger.debug(utils.print_vars(contact, depth=3))
    return True

