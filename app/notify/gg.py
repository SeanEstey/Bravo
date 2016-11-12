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

    logger.info(request.form.to_dict())

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
        logger.info('returned %s journal entries', response['count'])

    je = response['data']

    evnt_id = events.add(
        agency,
        request.form['event_name'] or request.form['query_name'],
        parse(request.form['delivery_date'])
    )

    trig_id = triggers.add(
        evnt_id,
        'voice_sms',
        parse(request.form['notific_date']).date(),
        parse(request.form['notific_time']).time()
    )

    refs = []
    for entry in je:
        refs.append(entry['accountRef'])

    try:
        accts = etap.call(
            'get_accounts_by_ref',
            conf['etapestry'],
            data={'refs':refs}
        )
    except Exception as e:
        msg = 'Failed to retrieve accts. %s' % str(e)
        logger.error(msg)
        raise EtapError(msg)

    # both je and accts lists should be same length, point to same account

    delivery_date = parse(request.form['delivery_date']).date()

    for i in range(len(je)):
        acct_id = accounts.add(
            agency,
            evnt_id,
            je[i]['accountName'],
            phone = etap.get_primary_phone(accts[i]),
            udf = {'amount': je[i]['amount']}
        )

        voice.add(
            evnt_id,
            delivery_date,
            trig_id,
            acct_id,
            etap.get_primary_phone(accts[i]),
            {'source': 'template',
             'template': 'voice/wsf/green_goods.html'},
            {'module': 'app.notify.pus',
             'func': 'on_call_interact'}
        )

    return True
