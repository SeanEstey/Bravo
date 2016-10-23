'''app.notify.voice'''

import logging
import os
from datetime import datetime
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import current_app, render_template, request
from pymongo.collection import ReturnDocument
from .. import db
from .. import utils, html
logger = logging.getLogger(__name__)


# TODO: remove all refs to 'status' outside 'tracking' dict. Redundant
# TODO: finish writing RFU code on call.status == 'failed'

#-------------------------------------------------------------------------------
def add(evnt_id, event_dt, trig_id, acct_id, to, on_answer, on_interact):
    '''
    @on_answer: {
        'source': 'template/audio',
        'template': 'path/to/template/file',
        'url': 'audio_url'}
    @on_interact: {
        'module':'module_name',
        'func':'handler_func'}
    '''

    return db['notifics'].insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': event_dt,
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
            'ended_dt': None
        }
    }).inserted_id


#-------------------------------------------------------------------------------
def call(notific, twilio_conf, voice_conf):
    '''Private method called by send()
    '''

    if notific['tracking']['attempts'] >= voice_conf['max_attempts']:
        return False

    try:
        client = TwilioRestClient(twilio_conf['api']['sid'], twilio_conf['api']['auth_id'])
    except TwilioRestException as e:
        logger.error('twilio REST error. %s', str(e))
        logger.debug('tb: ', exc_info=True)
        return 'failed'

    # Protect against sending real calls if in sandbox
    if os.environ.get('BRAVO_SANDBOX_MODE') == 'True':
        from_ = twilio_conf['voice']['valid_from_number']
    else:
        from_ = twilio_conf['voice']['number']

    call = None

    try:
        call = client.calls.create(
            from_ = from_,
            to = notific['to'],
            url ='%s/notify/voice/play/answer.xml' % os.environ.get('BRAVO_HTTP_HOST'),
            method = 'POST',
            if_machine = 'Continue',
            fallback_url = '%s/notify/voice/fallback' % os.environ.get('BRAVO_HTTP_HOST'),
            fallback_method = 'POST',
            status_callback = '%s/notify/voice/complete' % os.environ.get('BRAVO_HTTP_HOST'),
            status_events = ["completed"],
            status_method = 'POST')
    except Exception as e:
        logger.error('call to %s failed. %s', notific['to'], str(e))
        logger.debug('tb: ', exc_info=True)
    else:
        logger.info('%s call to %s', call.status, notific['to'])
        logger.debug(utils.print_vars(call))
    finally:
        db['notifics'].update_one({
            '_id': notific['_id']}, {
            '$set': {
                'tracking.status': call.status if call else 'failed',
                'tracking.sid': call.sid if call else None},
            '$inc': {'tracking.attempts':1}})
        return call.status if call else 'failed'

#-------------------------------------------------------------------------------
def get_speak(notific, template_path):
    '''Return rendered HMTL template as string
    Called inside Flask view so has context
    @notific: mongodb dict document
    @template_key: name of content dict containing file path
    '''

    account = db['accounts'].find_one({'_id':notific['acct_id']})

    try:
        speak = render_template(
            template_path,
            notific = notific,
            account = utils.formatter(
                account,
                to_local_time=True,
                to_strftime="%A, %B %d",
                bson_to_json=True),
        )
    except Exception as e:
        logger.error('get_speak: %s ', str(e))
        return 'Error'

    speak = html.clean_whitespace(speak)

    #logger.debug('speak template: %s', speak)

    return speak

#-------------------------------------------------------------------------------
def on_answer():
    '''User answered call. Get voice content.
    Working under request context
    Return: twilio.twiml.Response
    '''

    logger.debug('voice_play_answer args: %s', request.form)

    logger.info('%s %s (%s)',
        request.form['To'], request.form['CallStatus'], request.form.get('AnsweredBy'))

    notific = db['notifics'].find_one_and_update({
        'tracking.sid': request.form['CallSid']}, {
        '$set': {
            'tracking.status': request.form['CallStatus'],
            'tracking.answered_by': request.form.get('AnsweredBy')}},
        return_document=ReturnDocument.AFTER)

    # send_socket('update_msg',
    # {'id': str(msg['_id']), 'call_status': msg['call]['status']})

    response = twiml.Response()

    if notific['on_answer']['source'] == 'template':
        speak = get_speak(notific, notific['on_answer']['template'])

        response.say(speak, voice='alice')

        db['notifics'].update_one(
            {'tracking.sid': request.form['CallSid']},
            {'$set': {'tracking.speak': speak}}
        )
    elif notific['on_answer']['source'] == 'audio':
        response.play(notific['on_answer']['url'])

    response.gather(
        numDigits=1,
        action='%s/notify/voice/play/interact.xml' % os.environ.get('BRAVO_HTTP_HOST'),
        method='POST')

    return response

#-------------------------------------------------------------------------------
def on_interact():
    '''User has entered key input.
    Working under request context
    request contextuser has entered input. Invoke handler function to get response.
    Returns: twilio.twiml.Response
    '''

    logger.debug('on_interact: %s', request.form.to_dict())

    notific = db['notifics'].find_one_and_update({
          'tracking.sid': request.form['CallSid'],
        }, {
          '$set': {
            'tracking.digit': request.form['Digits']
        }},
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

    logger.debug('call_event args: %s', request.form)

    if request.form['CallStatus'] == 'completed':
        logger.info('%s %s (%s, %ss)',
            request.form['To'],
            request.form['CallStatus'],
            request.form.get('AnsweredBy'),
            request.form.get('CallDuration'))

    notific = db['notifics'].find_one_and_update({
        'tracking.sid': request.form['CallSid']}, {
        '$set': {
            'tracking.status': request.form['CallStatus'],
            'tracking.ended_dt': datetime.now(),
            'tracking.duration': request.form.get('CallDuration'),
            'tracking.answered_by': request.form.get('AnsweredBy')}},
        return_document=ReturnDocument.AFTER)

    if request.form['CallStatus'] == 'failed':
        logger.error('%s %s (%s)',
            request.form['To'], request.form['CallStatus'], request.form.get('SipResponseCode'))

        account = db['accounts'].find_one({
            '_id':notific['acct_id']})

        # TODO: is there an error 'description' arg passed on fails?
        from .. import tasks
        tasks.rfu.apply_async(
            args=[
                email['agency'],
                'Account %s error %s calling %s. %s' %(
                    account['id'], notific['to'], request.form.get('description')
                )
            ],
            kwargs={'_date': date.today().strftime('%-m/%-d/%Y')},
            queue=current_app.config['DB']
        )

    return 'OK'

#-------------------------------------------------------------------------------
def on_error():
    '''Twilio callback. Error.
    https://www.twilio.com/docs/api/errors/reference
    '''

    logger.error('call error. %s', request.form.to_dict())
    return 'OK'

