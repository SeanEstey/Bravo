'''app.notify.sms_announce'''
import os
import twilio
from flask import g, request
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from pymongo.collection import ReturnDocument
from app import get_keys, colors as c
from app.main.etapestry import call, get_prim_phone, EtapError, get_query
from . import events, accounts, triggers, voice, sms
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def add_event():

    log.debug(request.form.to_dict())

    try:
        accts = get_query(request.form['query_name'], category=request.form['query_category'])
    except Exception as e:
        msg = 'Failed to retrieve query "%s". Details: %s' % (request.form['query_name'], str(e))
        log.exception(msg)
        raise EtapError(msg)

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

        sms.add(
            evnt_id,
            event_date,
            trig_id,
            acct_id,
            get_prim_phone(accts[i]),
            {'source': 'template',
             'template': 'sms/%s/announce.html' % g.group}
             'url': request.form['audio_url']},
            {'module': 'app.notify.voice_announce',
             'func': 'on_interact'}
        )

    log.info('SMS announce event created')
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


        from twilio.twiml.messaging_response import MessagingResponse
        response = MessagingResponse()

        response.play(notific['on_answer']['audio_url'], voice='alice')

        response.gather(
            num_digits=1,
            action="%s/notify/voice/play/interact.xml" % os.environ.get('BRV_HTTP_HOST'),
            method='POST')

        return response
