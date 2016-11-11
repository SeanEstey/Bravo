'''app.notify.gg'''

import logging
import os
import json
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import current_app, render_template, request
from flask_login import current_user
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from bson.objectid import ObjectId as oid
from bson import json_util

from .. import utils, parser, gcal, etap
from .. import db
from . import events, email, sms, voice, triggers, accounts
logger = logging.getLogger(__name__)


class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def add_event():
    agency = db.users.find_one({'user': current_user.username})['agency']
    conf= db.agencies.find_one({'name':agency})

    try:
        response = etap.call(
            'get_query_accounts',
            conf['etapestry'],
            data={
                'query': request.form['query_name'],
                'query_category':'GG: Invoices'
            }
        )
    except Exception as e:
        msg = 'Failed to retrieve query "%s". Details: %s' % (request.form['query_name'], str(e))
        logger.error(msg)
        raise EtapError(msg)
    else:
        logger.info(response)
        #if len(etap_accts) < 1:
        #    raise EtapError('eTap query for Block %s is empty' % block)

    return True
