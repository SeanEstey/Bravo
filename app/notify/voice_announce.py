'''app.notify.voice_announce'''
import twilio
import logging, os
from flask import g, request, current_app
from flask_login import current_user
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
from pymongo.collection import ReturnDocument
from . import events, accounts, triggers, voice
from .. import get_keys, utils, etap
from app.utils import bcolors
log = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def add_event():
    log.debug(request.form.to_dict())

    try:
        response = etap.call(
            'get_query',
            get_keys('etapestry'),
            data={
                'query': request.form['query_name'],
                'query': request.form['query_category']
            }
        )
    except Exception as e:
        msg = \
            'Failed to retrieve query "%s". Msg=%s' %(
            request.form['query_name'], str(e))
        log.error(msg)
        raise EtapError(msg)
    else:
        log.debug('returned %s accounts', response['count'])

    evnt_id = events.add(
        g.user.agency,
        request.form['event_name'] or request.form['query_name'],
        parse(request.form['event_date']),
        'recorded_announcement')

    trig_id = triggers.add(
        evnt_id,
        'voice_sms',
        parse(request.form['notific_date']).date(),
        parse(request.form['notific_time']).time())

    accts = response['data']
    event_date = parse(request.form['event_date']).date()

    for i in range(len(accts)):
        acct_id = accounts.add(
            g.user.agency,
            evnt_id,
            accts[i]['name'],
            phone = etap.get_prim_phone(accts[i]))

        voice.add(
            evnt_id,
            event_date,
            trig_id,
            acct_id,
            etap.get_prim_phone(accts[i]),
            {'source': 'audio',
             'url': request.form['audio_url']},
            {'module': 'app.notify.voice_announce',
             'func': 'on_interact'}
        )

    log.info(
        '%s voice_announce event successfully created %s',
        bcolors.OKGREEN, bcolors.ENDC)

    return evnt_id

#-------------------------------------------------------------------------------
def on_interact():
    if request.form.get('Digits') == '1':
        notific = g.db['notifics'].find_one_and_update({
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
            action="%s/notify/voice/play/interact.xml" % os.environ.get('BRV_HTTP_HOST'),
            method='POST')

        return voice
