'''app.notify.sms_announce'''
import os
import twilio
from flask import g, request
from datetime import datetime, date, time, timedelta
from dateutil.parser import parse
from pymongo.collection import ReturnDocument
from app import get_keys
from app.lib.loggy import Loggy, colors as c
from app.main.etap import call, get_prim_phone, EtapError
from . import events, accounts, triggers, voice, sms
log = Loggy('notify.sms_annc')

#-------------------------------------------------------------------------------
def add_event():
    agency = g.db.users.find_one({'user': g.user.user_id})['agency']
    conf= g.db.agencies.find_one({'name':agency})

    log.debug(request.form.to_dict())

    try:
        response = call(
            'get_query',
            conf['etapestry'],
            data={
                'query': request.form['query_name'],
                'category': request.form['query_category']
            }
        )
    except Exception as e:
        msg = 'Failed to retrieve query "%s". Details: %s' % (request.form['query_name'], str(e))
        log.error(msg)
        raise EtapError(msg)
    else:
        log.debug('returned %s accounts', response['count'])

    evnt_id = events.add(
        agency,
        request.form['event_name'] or request.form['query_name'],
        parse(request.form['event_date']),
        'recorded_announcement'
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
            phone = get_prim_phone(accts[i])
        )

        sms.add(
            evnt_id,
            event_date,
            trig_id,
            acct_id,
            get_prim_phone(accts[i]),
            {'source': 'template',
             'template': 'sms/%s/announce.html' % agency}
             'url': request.form['audio_url']},
            {'module': 'app.notify.voice_announce',
             'func': 'on_interact'}
        )

    log.info(
        '%s sms_announce event successfully created %s',
        c.GRN, c.ENDC)

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
