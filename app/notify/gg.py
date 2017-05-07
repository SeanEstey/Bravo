'''app.notify.gg'''
import os
from twilio import twiml
from flask import g, request
from dateutil.parser import parse
from .. import get_keys
from app.main.etap import call, get_prim_phone, EtapError
from . import events, email, sms, voice, triggers, accounts
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def add_event():

    log.debug(request.form.to_dict())

    try:
        response = call(
            'get_query',
            get_keys('etapestry'),
            data={
                'query': request.form['query_name'],
                'category':'GG: Invoices'})
    except Exception as e:
        msg = 'Failed to retrieve query "%s". Details: %s' % (request.form['query_name'], str(e))
        log.error(msg)
        raise EtapError(msg)
    else:
        log.debug('returned %s journal entries', response['count'])

    je = response['data']

    evnt_id = events.add(
        g.user.agency,
        request.form['event_name'] or request.form['query_name'],
        parse(request.form['event_date']),
        'green_goods')

    trig_id = triggers.add(
        evnt_id,
        'voice_sms',
        parse(request.form['notific_date']).date(),
        parse(request.form['notific_time']).time())

    refs = []
    for entry in je:
        refs.append(entry['accountRef'])

    try:
        accts = call(
            'get_accts_by_ref',
            get_keys('etapestry'),
            data={'acct_refs':refs})
    except Exception as e:
        msg = 'Failed to retrieve accts. %s' % str(e)
        #log.error(msg)
        raise EtapError(msg)

    # both je and accts lists should be same length, point to same account

    delivery_date = parse(request.form['event_date']).date()

    for i in range(len(je)):
        acct_id = accounts.add(
            g.user.agency,
            evnt_id,
            je[i]['accountName'],
            phone = get_prim_phone(accts[i]),
            udf = {'amount': je[i]['amount']})

        voice.add(
            evnt_id,
            delivery_date,
            trig_id,
            acct_id,
            get_prim_phone(accts[i]),
            {'source': 'template',
             'template': 'voice/wsf/green_goods.html'},
            {'module': 'app.notify.gg',
             'func': 'on_call_interact'})

    return evnt_id

#-------------------------------------------------------------------------------
def on_call_interact(notific):

    response = twiml.Response()

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
            numDigits=1,
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
