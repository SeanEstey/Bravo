'''app.notify.gg'''
import logging, os
from twilio import twiml
from flask import g, request
from dateutil.parser import parse
from .. import get_keys, etap
from . import events, email, sms, voice, triggers, accounts
log = logging.getLogger(__name__)

class EtapError(Exception):
    pass

#-------------------------------------------------------------------------------
def add_event():
    log.info(request.form.to_dict())

    try:
        response = etap.call(
            'get_query',
            get_keys('etapestry'),
            data={
                'query': request.form['query_name'],
                'category':'GG: Invoices'
            }
        )
    except Exception as e:
        msg = 'Failed to retrieve query "%s". Details: %s' % (request.form['query_name'], str(e))
        log.error(msg)
        raise EtapError(msg)
    else:
        log.info('returned %s journal entries', response['count'])

    je = response['data']

    evnt_id = events.add(
        g.user.agency,
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

    refs = []
    for entry in je:
        refs.append(entry['accountRef'])

    try:
        accts = etap.call(
            'get_accts_by_ref',
            conf['etapestry'],
            data={'acct_refs':refs}
        )
    except Exception as e:
        msg = 'Failed to retrieve accts. %s' % str(e)
        log.error(msg)
        raise EtapError(msg)

    # both je and accts lists should be same length, point to same account

    delivery_date = parse(request.form['event_date']).date()

    for i in range(len(je)):
        acct_id = accounts.add(
            g.user.agency,
            evnt_id,
            je[i]['accountName'],
            phone = etap.get_prim_phone(accts[i]),
            udf = {'amount': je[i]['amount']}
        )

        voice.add(
            evnt_id,
            delivery_date,
            trig_id,
            acct_id,
            etap.get_prim_phone(accts[i]),
            {'source': 'template',
             'template': 'voice/wsf/green_goods.html'},
            {'module': 'app.notify.gg',
             'func': 'on_call_interact'}
        )

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

        response.gather(
            action= '%s/notify/voice/play/interact.xml' % os.environ.get('BRV_HTTP_HOST'),
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
