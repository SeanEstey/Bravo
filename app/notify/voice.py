'''app.notify.voice'''
import logging, os
from datetime import datetime, date, time
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import g, render_template, request
from pymongo.collection import ReturnDocument
from .. import get_logger, smart_emit, utils, html
from app.dt import to_utc
log = get_logger('notify.voice')

#-------------------------------------------------------------------------------
def add(evnt_id, event_date, trig_id, acct_id, to, on_answer, on_interact):
    '''
    @on_answer: {
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
        'to': utils.to_intl_format(to),
        'type': 'voice',
        'tracking': {
            'status': 'pending',
            'sid': None,
            'duration': None,
            'answered_by': None,
            'attempts': 0,
            'ended_dt': None}}).inserted_id

#-------------------------------------------------------------------------------
def call(notific, twilio_conf, voice_conf):
    '''Private method called by send()
    '''

    if notific['tracking']['attempts'] >= voice_conf['max_attempts']:
        return False

    try:
        client = TwilioRestClient(twilio_conf['api']['sid'], twilio_conf['api']['auth_id'])
    except TwilioRestException as e:
        log.error('twilio REST error. %s', str(e))
        log.debug('tb: ', exc_info=True)
        return 'failed'

    # Protect against sending real calls if in sandbox
    if os.environ.get('BRV_SANDBOX') == 'True':
        from_ = twilio_conf['voice']['valid_from_number']
    else:
        from_ = twilio_conf['voice']['number']

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
        log.debug('tb: ', exc_info=True)
    else:
        log.debug('%s call to %s', call.status, notific['to'])
        #log.debug(utils.print_vars(call))
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
            notific = utils.formatter(
                notific,
                to_local_time=True,
                to_strftime="%A, %B %d"),
            account = utils.formatter(
                account,
                to_local_time=True,
                to_strftime="%A, %B %d",
                bson_to_json=True),
            timeout=timeout)
    except Exception as e:
        log.error('get_speak: %s ', str(e))
        return 'Error'

    speak = html.clean_whitespace(speak)

    #log.debug('speak template: %s', speak)

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

    smart_emit('notific_status', {
        'notific_id': str(notific['_id']),
        'status': request.form['CallStatus']})

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

    #log.debug('call_event args: %s', request.form)

    if request.form['CallStatus'] == 'completed':
        log.info('completed voice notific to %s (%s, %ss)',
            request.form['To'],
            request.form.get('AnsweredBy'),
            request.form.get('CallDuration'))

    notific = g.db.notifics.find_one_and_update({
        'tracking.sid': request.form['CallSid']}, {
        '$set': {
            'tracking.status': request.form['CallStatus'],
            'tracking.ended_dt': datetime.now(),
            'tracking.duration': request.form.get('CallDuration'),
            'tracking.answered_by': request.form.get('AnsweredBy')}},
        return_document=ReturnDocument.AFTER)

    if request.form['CallStatus'] == 'failed':
        log.error('%s %s (%s)',
            request.form['To'], request.form['CallStatus'], request.form.get('SipResponseCode'))

        account = g.db.accounts.find_one({
            '_id':notific['acct_id']})

        evnt = g.db.notific_events.find_one({'_id':notific['evnt_id']})

        from app.main.tasks import create_rfu
        create_rfu.delay(
            evnt['agency'],
            'Error calling %s. %s' %(
                notific['to'], request.form.get('description')),
            options={
                'Account Number': account['udf'].get('etap_id'),
                'Name & Address': account['name'],
                'Date': date.today().strftime('%-m/%-d/%Y')})

    smart_emit('notific_status', {
        'notific_id': str(notific['_id']),
        'status': request.form['CallStatus'],
        'answered_by': request.form.get('AnsweredBy'),
        'description': request.form.get('description')})

    return 'OK'

#-------------------------------------------------------------------------------
def on_error():
    '''Twilio callback. Error.
    https://www.twilio.com/docs/api/errors/reference
    '''

    from . import err_codes
    code = str(request.form['ErrorCode'])
    log.error('twilio error code %s: %s', code, err_codes.TWILIO_ERR[code])
    log.debug('call dump: %s', request.form.to_dict())
    return 'OK'

