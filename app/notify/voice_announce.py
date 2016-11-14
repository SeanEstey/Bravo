'''app.notify.voice_announce'''

import twilio
import logging
from flask import request, current_app
import os
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
from pymongo.collection import ReturnDocument

from app import db
from . import events, accounts, triggers, voice
from .. import utils, etap
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
                'query_category': request.form['query_category']
            }
        )
    except Exception as e:
        msg = 'Failed to retrieve query "%s". Details: %s' % (request.form['query_name'], str(e))
        logger.error(msg)
        raise EtapError(msg)
    else:
        logger.info('returned %s accounts', response['count'])

    evnt_id = events.add(
        agency,
        request.form['event_name'] or request.form['query_name'],
        parse(request.form['event_date']),
        'green_goods'
    )

    trig_id = triggers.add(
        evnt_id,
        'voice_sms',
        parse(request.form['notific_date']).date(),
        parse(request.form['notific_time']).time()
    )

    accts = response['data']

    event_date = parse(request.form['event_date']).date()

    for i in range(len(accts)):
        acct_id = accounts.add(
            agency,
            evnt_id,
            accts[i]['name'],
            phone = etap.get_primary_phone(accts[i])
        )

        voice.add(
            evnt_id,
            event_date,
            trig_id,
            acct_id,
            etap.get_primary_phone(accts[i]),
            {'source': 'audio',
             'url': request.form['audio_url']},
            {'module': 'app.notify.voice_announce',
             'func': 'on_interact'}
        )

    return evnt_id

#-------------------------------------------------------------------------------
def on_interact():
    if request.form.get('Digits') == '1':
        notific = db['notifics'].find_one_and_update({
              'tracking.sid': request.form['CallSid'],
            }, {
              '$set': {
                'tracking.digit': request.form['Digits']
            }},
            return_document=ReturnDocument.AFTER)

        voice = twilio.twiml.Response()

        voice.play(notific['on_answer']['audio_url'], voice='alice')

        voice.gather(
            numDigits=1,
            action="%s/notify/voice/play/interact.xml" % os.environ.get('BRAVO_HTTP_HOST'),
            method='POST')

        return voice
