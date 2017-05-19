'''app.notify.voice'''
import os, time, urllib
from time import sleep
from datetime import datetime, date, time
from bson import ObjectId as oid
from twilio import TwilioRestException, twiml
from twilio.rest import TwilioRestClient
from twilio.util import TwilioCapability
from flask import g, render_template, request, Response
from pymongo.collection import ReturnDocument
from app import get_keys, colors as c
from app.lib import html
from app.lib.dt import to_utc
from .utils import intrntl_format, simple_dict
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def add(evnt_id, event_date, trig_id, acct_id, to, on_answer, on_interact):
    '''@on_answer: {
        'source': 'template/audio',
        'template': 'path/to/template/file',
        'url': 'audio_url'}
    @on_interact: {
        'module':'module_name',
        'func':'handler_func'}
    '''

    return g.db.notifics.insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': to_utc(d=event_date, t=time(8,0)),
        'on_answer': on_answer,
        'on_interact': on_interact,
        'to': intrntl_format(to),
        'type': 'voice',
        'tracking': {
            'status': 'pending',
            'sid': None,
            'duration': None,
            'answered_by': None,
            'attempts': 0,
            'ended_dt': None}}).inserted_id

#-------------------------------------------------------------------------------
def call(notific, conf):
    '''Private method called by send()
    '''

    try:
        client = TwilioRestClient(conf['api']['sid'], conf['api']['auth_id'])
    except TwilioRestException as e:
        log.error('twilio REST error. %s', str(e))
        log.exception(str(e))
        return 'failed'

    # Protect against sending real calls if in sandbox
    if os.environ.get('BRV_SANDBOX') == 'True':
        from_ = conf['voice']['valid_from_number']
    else:
        from_ = conf['voice']['number']

    call = None
    http_host = os.environ.get('BRV_HTTP_HOST')
    if http_host.find('https') == 0:
        http_host = http_host.replace('https', 'http')

    try:
        call = client.calls.create(
            from_ = from_,
            to = notific['to'],
            url ='%s/notify/voice/play/answer.xml' % http_host,
            method = 'POST',
            if_machine = 'Continue',
            fallback_url = '%s/notify/voice/fallback' % http_host,
            fallback_method = 'POST',
            status_callback = '%s/notify/voice/complete' % http_host,
            status_events = ["completed"],
            status_method = 'POST')
    except Exception as e:
        log.error('call to %s failed. %s', notific['to'], str(e))
        log.exception(str(e))
    else:
        log.debug('%s call to %s', call.status, notific['to'])
    finally:
        g.db.notifics.update_one({
            '_id': notific['_id']}, {
            '$set': {
                'tracking.status': call.status if call else 'failed',
                'tracking.sid': call.sid if call else None},
            '$inc': {'tracking.attempts':1}})

        return call.status if call else 'failed'

#-------------------------------------------------------------------------------
def get_speak(notific, template_path, timeout=False):
    '''Return rendered HMTL template as string
    Called inside Flask view so has context
    @notific: mongodb dict document
    @template_key: name of content dict containing file path
    '''

    account = g.db.accounts.find_one({'_id':notific['acct_id']})

    try:
        speak = render_template(
            template_path,
            notific = simple_dict(notific),
            account = simple_dict(account),
            timeout=timeout)
    except Exception as e:
        log.error('get_speak: %s ', str(e))
        return 'Error'

    speak = html.clean_whitespace(speak)
    return speak

#-------------------------------------------------------------------------------
def on_answer():
    '''User answered call. Get voice content.
    Working under request context
    Return: twilio.twiml.Response
    '''

    #log.debug('voice_play_answer args: %s', request.form)

    log.debug('%s %s (%s)',
        request.form['To'], request.form['CallStatus'], request.form.get('AnsweredBy'))

    notific = g.db.notifics.find_one_and_update({
        'tracking.sid': request.form['CallSid']}, {
        '$set': {
            'tracking.status': request.form['CallStatus'],
            'tracking.answered_by': request.form.get('AnsweredBy')}},
        return_document=ReturnDocument.AFTER)

    '''smart_emit('notific_status', {
        'notific_id': str(notific['_id']),
        'status': request.form['CallStatus']})'''

    response = twiml.Response()

    http_host = os.environ['BRV_HTTP_HOST']
    if http_host.find('https') == 0:
        http_host = http_host.replace('https', 'http')

    if notific['on_answer']['source'] == 'template':
        if request.form['AnsweredBy'] == 'human':
            response.say(
                get_speak(notific, notific['on_answer']['template']),
                voice='alice')

            response.gather(
                action='%s/notify/voice/play/interact.xml' % http_host,
                method='POST',
                numDigits=1,
                timeout=10)

            # Entering digit triggers action URL
            # This response only executes if timeout, either if this is a
            # machine misdetected as human, or if human fails to press key
            response.say(
                get_speak(notific, notific['on_answer']['template'], timeout=True),
                voice='alice')

            response.hangup()

        elif request.form['AnsweredBy'] == 'machine':
            response.say(
                get_speak(notific, notific['on_answer']['template']),
                voice='alice')
            response.hangup()

        g.db.notifics.update_one(
            {'tracking.sid': request.form['CallSid']},
            {'$set': {'tracking.speak': str(response).replace('\"', '')}})
    elif notific['on_answer']['source'] == 'audio':
        response.play(notific['on_answer']['url'])

        response.gather(
            numDigits=1,
            action='%s/notify/voice/play/interact.xml' % http_host,
            method='POST')

    return response

#-------------------------------------------------------------------------------
def on_interact():
    '''User has entered key input.
    Working under request context
    request contextuser has entered input. Invoke handler function to get response.
    Returns: twilio.twiml.Response
    '''

    #log.debug('on_interact: %s', request.form.to_dict())

    notific = g.db.notifics.find_one_and_update(
        {'tracking.sid': request.form['CallSid']},
        {'$set': {'tracking.digit': request.form['Digits']}},
        return_document=ReturnDocument.AFTER)

    # Import assigned handler module and invoke function
    # to get voice response

    module = __import__(notific['on_interact']['module'], fromlist='.' )
    handler_func = getattr(module, notific['on_interact']['func'])
    return handler_func(notific)

#-------------------------------------------------------------------------------
def on_complete():
    '''Twilio call is complete. Create RFU if failed.
    Working under request context
    '''

    form = request.form

    if request.form['CallStatus'] == 'completed':
        log.debug('%sdelivered voice notific to %s%s (%s, %ss)',
            c.GRN, form['To'], c.ENDC, form['AnsweredBy'], form['CallDuration'])

    notific = g.db.notifics.find_one_and_update({
        'tracking.sid': form['CallSid']}, {
        '$set': {
            'tracking.status': form['CallStatus'],
            'tracking.ended_dt': datetime.now(),
            'tracking.duration': form.get('CallDuration'),
            'tracking.answered_by': form.get('AnsweredBy')}},
        return_document=ReturnDocument.AFTER)

    if form['CallStatus'] == 'failed':
        sleep(5)
        desc = form.get('description')
        agency = g.db.agencies.find_one({'twilio.api.sid': form['AccountSid']})
        keys = agency['twilio']['api']
        client = TwilioRestClient(keys['sid'], keys['auth_id'])
        call_sid = form['CallSid']

        for n in client.notifications.list():
            if n.call_sid == call_sid:
                desc = urllib.unquote(n.message_text).replace('+', ' ').replace('&',' ')
                break

        log.error('%s %s (%s)', form['To'], form['CallStatus'], desc)

        acct = g.db.accounts.find_one({'_id':notific['acct_id']})
        evnt = g.db.events.find_one({'_id':notific['evnt_id']})

        from app.main.tasks import create_rfu
        create_rfu.delay(
            evnt['agency'],
            'Error calling %s\n. %s' %(notific['to'], desc),
            options={
                'ID': acct['udf'].get('etap_id'),
                'Account': acct['name']})

    '''smart_emit('notific_status', {
        'notific_id': str(notific['_id']),
        'status': form['CallStatus'],
        'answered_by': form.get('AnsweredBy'),
        'description': form.get('description')})'''

    return 'OK'

#-------------------------------------------------------------------------------
def on_error():
    '''Twilio callback. Error.
    https://www.twilio.com/docs/api/errors/reference
    '''

    log.debug('voice fallback on_error()')
    from .err_codes import TWILIO_ERRS
    code = str(request.form['ErrorCode'])
    log.error('twilio error code %s: %s', code, TWILIO_ERRS[code])
    log.debug('call dump: %s', request.form.to_dict())
    return 'OK'

#-------------------------------------------------------------------------------
def get_token():
    '''Get token for client to make preview voice call
    '''

    log.debug('generating twilio token...')

    api = get_keys('twilio')['api']
    app_sid = get_keys('twilio')['sms']['app_sid']

    try:
        capability = TwilioCapability(api['sid'], api['auth_id'])
        capability.allow_client_outgoing(app_sid)
        token = capability.generate()
    except Exception as e:
        log.error('error gen. twilio token: %s', str(e))
        log.debug('',exc_info=True)
        return str(e)

    return token

#-------------------------------------------------------------------------------
def preview():

    evnt_id = oid(request.form.get('evnt_id'))
    log.debug('playing voice preview (evnt_id="%s")', str(evnt_id))
    evnt = g.db.events.find_one({'_id':evnt_id})
    notific = g.db.notifics.find_one({'evnt_id':evnt_id, 'type':'voice'})

    if not notific:
        log.error('Notification not found for Preview', extra={'request':request.form})
        return "False"

    notific['tracking']['answered_by'] = 'human'
    notific['tracking']['digit'] = "1"
    acct = g.db.accounts.find_one({'_id':notific['acct_id']})

    speak = get_speak(notific, notific['on_answer']['template'], timeout=False)
    response = twiml.Response()
    response.say(speak, voice='alice')
    return response
