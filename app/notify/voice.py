'''app.notify.voice'''

import logging
from datetime import datetime
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import current_app, render_template
from pymongo.collection import ReturnDocument
from .. import db
from .. import utils
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
        'to': to,
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

    if notific['to'][0:2] != "+1":
        to = "+1" + notific['to']

    PUB_URL = current_app.config['PUB_URL']

    try:
        client = TwilioRestClient(
          twilio_conf['api_keys']['main']['sid'],
          twilio_conf['api_keys']['main']['auth_id']
        )
    except TwilioRestException as e:
        logger.error('Call not made. Could not get Twilio client. %s', str(e))
        pass

    call = client.calls.create(
        from_ = twilio_conf['ph'],
        to = to,
        url ='%s/notify/voice/play/answer.xml' % PUB_URL,
        method = 'POST',
        if_machine = 'Continue',
        fallback_url = '%s/notify/voice/fallback' % PUB_URL,
        fallback_method = 'POST',
        status_callback = '%s/notify/voice/complete' % PUB_URL,
        status_events = ["completed"],
        status_method = 'POST'
    )

    logger.debug(vars(call))

    db['notifics'].update_one({
        '_id': notific['_id']}, {
        '$set': {
            'tracking.status': call.status,
            'tracking.sid': call.sid or None},
        '$inc': {'tracking.attempts':1}})

    logger.info('Call %s for %s', call.status, notific['to'])

    return call.status

#-------------------------------------------------------------------------------
def get_speak(notific, template_file):
    '''Return rendered HMTL template as string
    Called inside Flask view so has context
    @notific: mongodb dict document
    @template_key: name of content dict containing file path
    '''

    account = db['accounts'].find_one({'_id':notific['acct_id']})

    # need an application context for access/editing of apps SERVER_NAME variable,
    # which underlying url_for() requires so it's aware of the domain address
    with current_app.app_context():
        # Required even though voice templates aren't calling url_for()
        # function. No idea why...
        current_app.config['SERVER_NAME'] = current_app.config['PUB_URL']
        try:
            content = render_template(
                template_file,
                medium='voice',
                account = utils.formatter(
                    account,
                    to_local_time=True,
                    to_strftime="%A, %B %d",
                    bson_to_json=True),
                call = {
                    'digit': notific.get('digit') or None,
                    'answered_by': notific['answered_by']
                }
            )
        except Exception as e:
            logger.error('get_speak: %s ', str(e))
            return 'Error'
        current_app.config['SERVER_NAME'] = None

    content = content.replace("\n", "")
    content = content.replace("  ", "")

    logger.debug('speak template: %s', content)

    db['notifics'].update_one({'_id':notific['_id']},{'$set':{'speak':content}})

    return content

#-------------------------------------------------------------------------------
def on_answer(args):
    '''User answered call. Get voice content.
    Return: twilio.twiml.Response
    '''

    logger.debug('voice_play_answer args: %s', args)

    logger.info('%s %s (%s)',
        args['To'], args['CallStatus'], args.get('AnsweredBy'))

    notific = db['notifics'].find_one_and_update({
        'tracking.sid': args['CallSid']}, {
        '$set': {
            'tracking.status': args['CallStatus'],
            'tracking.answered_by': args.get('AnsweredBy')}},
        return_document=ReturnDocument.AFTER)

    # send_socket('update_msg',
    # {'id': str(msg['_id']), 'call_status': msg['call]['status']})

    # Html template content or audio url?

    response = twiml.Response()

    if notific['on_answer']['source'] == 'template':
        response.say(
            get_speak(
                db['accounts'].find_one({'_id':notific['acct_id']}),
                notific,
                notific['on_answer']['template'],
            voice='alice'))
    elif notific['on_answer']['source'] == 'audio':
        response.play(notific['on_answer']['url'])

    # All voice templates prompt key "1" to repeat message

    response.gather(
        numDigits=1,
        action='%s/notify/voice/play/interact.xml' % current_app.config['PUB_URL'],
        method='POST')

    return response

#-------------------------------------------------------------------------------
def on_interact(args):
    '''User has entered key input.
    Working under request context
    request contextuser has entered input. Invoke handler function to get response.
    Returns: twilio.twiml.Response
    '''

    logger.debug('voice_play_interact args: %s', args)

    notific = db['notifics'].find_one({'tracking.sid': args['CallSid']})

    # Import assigned handler module and invoke function
    # to get voice response

    module = __import__(notific['on_interact']['module'])
    handler_func = getattr(module, notific['on_interact']['func'])

    response = handler_func(notific, args)
    return response

#-------------------------------------------------------------------------------
def on_complete(args):
    '''Twilio call is complete. Create RFU if failed.
    '''

    logger.debug('call_event args: %s', args)

    if args['CallStatus'] == 'completed':
        logger.info('%s %s (%s, %ss)',
            args['To'], args['CallStatus'], args.get('AnsweredBy'), args.get('CallDuration'))

    notific = db['notifics'].find_one_and_update({
        'tracking.sid': args['CallSid']}, {
        '$set': {
            'tracking.status': args['CallStatus'],
            'tracking.ended_dt': datetime.now(),
            'tracking.duration': args.get('CallDuration'),
            'tracking.answered_by': args.get('AnsweredBy')}},
        return_document=ReturnDocument.AFTER)

    if args['CallStatus'] == 'failed':
        logger.error('%s %s (%s)',
            args['To'], args['CallStatus'], args.get('SipResponseCode'))

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
def strip_phone(to):
    if not to:
        return ''
    return to.replace(' ', '').replace('(','').replace(')','').replace('-','')
