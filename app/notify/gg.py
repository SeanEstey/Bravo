'''app.notify.gg'''
import os
from flask import g, request
from dateutil.parser import parse
from .. import get_keys
from app.main.etap import get_prim_phone, EtapError, get_query, get_acct
from . import events, email, sms, voice, triggers, accounts
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def add_event():

    query = request.form['query_name']
    name = request.form['event_name'] or query
    event_dt = parse(request.form['event_date'])
    notific_d = parse(request.form['notific_date']).date()
    notific_t = parse(request.form['notific_time']).time()

    try:
        orders = get_query(query, category='GG: Invoices', cache=True)
    except Exception as e:
        log.exception('Failed to retrieve GG invoice query="%s".', query)
        raise

    event_id = events.add(g.group, name, event_dt, 'green_goods')
    trig_id = triggers.add(event_id, 'voice_sms', notific_d, notific_t)
    delivery_d = event_dt.date()

    for i in range(0, len(orders)):
        acct = get_acct(None, ref=orders[i]['accountRef'])
        evnt_db_acct_id = accounts.add(
            g.group, event_id, orders[i]['accountName'],
            phone = get_prim_phone(acct),
            udf = {'amount': orders[i]['amount']})
        voice.add(
            event_id, delivery_d, trig_id, evnt_db_acct_id, get_prim_phone(acct),
            {'source': 'template', 'template': 'voice/wsf/green_goods.html'},
            {'module': 'app.notify.gg', 'func': 'on_call_interact'})

    return event_id

#-------------------------------------------------------------------------------
def on_call_interact(notific):

    from twilio.twiml.voice_response import VoiceResponse
    response = VoiceResponse()

    # Digit 1: Play live message
    if request.form['Digits'] == '1':
        response.say(
            voice.get_speak(
              notific,
              notific['on_answer']['template']),
            voice='alice')

        http_host = os.environ.get('BRV_HTTP_HOST')
        http_host = http_host.replace('https','http') if http_host.find('https') == 0 else http_host

        response.gather(
            action= '%s/notify/voice/play/interact.xml' % http_host,
            method='POST',
            num_digits=1,
            timeout=10)

        response.say(
            voice.get_speak(
              notific,
              notific['on_answer']['template'],
              timeout=True),
            voice='alice')

        response.hangup()

        return response
    elif request.form['Digits'] == '2':
        response.say(
            voice.get_speak(
              notific,
              notific['on_answer']['template']),
            voice='alice')

        response.hangup()

        return response
