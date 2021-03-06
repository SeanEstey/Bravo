'''app.notify.voice_announce'''
from os import environ as env
import logging, twilio
from flask import g, request, current_app
from flask_login import current_user
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
from pymongo.collection import ReturnDocument
from app import get_keys
from app.main.etapestry import call, get_prim_phone, EtapError, get_query
from . import events, accounts, triggers, voice
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def add_event():

    try:
        accts = get_query(request.form['query_name'], category=request.form['query_category'])
    except Exception as e:
        log.exception('Failed to retrieve query %s', request.form['query_name'])
        raise EtapError(e.message)

    evnt_id = events.add(
        g.group,
        request.form['event_name'] or request.form['query_name'],
        parse(request.form['event_date']),
        'recorded_announcement')

    trig_id = triggers.add(
        evnt_id,
        'voice_sms',
        parse(request.form['notific_date']).date(),
        parse(request.form['notific_time']).time())

    event_date = parse(request.form['event_date']).date()

    for i in range(len(accts)):
        acct_id = accounts.add(
            g.group,
            evnt_id,
            accts[i]['name'],
            phone = get_prim_phone(accts[i]))

        voice.add(
            evnt_id,
            event_date,
            trig_id,
            acct_id,
            get_prim_phone(accts[i]),
            {'source': 'audio',
             'url': request.form['audio_url']},
            {'module': 'app.notify.voice_announce',
             'func': 'on_interact'}
        )

    log.info('Voice announcement created')
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

        from twilio.twiml.voice_response import VoiceResponse
        voice = VoiceResponse()

        voice.play(notific['on_answer']['audio_url'], voice='alice')

        host = env.get('BRV_HTTP_HOST')
        host = host.replace('https','http') if host.find('https') == 0 else host

        voice.gather(
            num_digits=1,
            action="%s/notify/voice/play/interact.xml" % host,
            method='POST')

        return voice
