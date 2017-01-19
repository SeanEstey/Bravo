'''app.notify.recording'''

from twilio import twiml
import os
import logging
from datetime import datetime,date,time,timedelta
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import request, current_app
from flask_login import current_user
from .. import smart_emit, get_db, utils
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def dial():
    '''Request: POST from Bravo javascript client with 'To' arg
    Response: JSON dict {'status':'string'}
    '''

    db = get_db()

    agency = db['users'].find_one({'user': current_user.user_id})['agency']

    logger.info('Record audio request from ' + request.form['To'])

    twilio = db['agencies'].find_one({'name':agency})['twilio']

    try:
        client = TwilioRestClient(twilio['api']['sid'], twilio['api']['auth_id'])
    except TwilioRestException as e:
        logger.error('twilio REST error. %s', str(e))
        logger.debug('tb: ', exc_info=True)
        return 'failed'

    call = None

    try:
        call = client.calls.create(
            from_ = twilio['voice']['number'],
            to = request.form['To'],
            url ='%s/notify/record/answer.xml' % os.environ.get('BRAVO_HTTP_HOST'),
            method = 'POST',
            if_machine = 'Continue',
            fallback_url = '%s/notify/voice/fallback' % os.environ.get('BRAVO_HTTP_HOST'),
            fallback_method = 'POST',
            status_callback = '%s/notify/record/complete' % os.environ.get('BRAVO_HTTP_HOST'),
            status_events = ["completed"],
            status_method = 'POST')
    except Exception as e:
        logger.error('call to %s failed. %s', request.form['To'], str(e))
        return {'status':'failed', 'description': 'Invalid phone number'}
    else:
        logger.debug(utils.print_vars(call))

        db.audio.insert_one({
            'date': datetime.utcnow(),
            'sid': call.sid,
            'agency': agency,
            'to': call.to,
            'from': call.from_,
            'status': call.status,
            'direction': call.direction
        })


    return {'status':call.status}

#-------------------------------------------------------------------------------
def on_answer():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    # Record voice message
    voice = twiml.Response()
    voice.say('Record your message after the beep. Press pound when complete.',
      voice='alice'
    )
    voice.record(
        method= 'POST',
        action= '%s/notify/record/interact.xml' % os.environ.get('BRAVO_HTTP_HOST'),
        playBeep= True,
        finishOnKey='#',
        timeout=120
    )

    smart_emit('record_audio', {'status':'answered'})

    return voice

#-------------------------------------------------------------------------------
def on_interact():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    logger.debug('on_interact: %s', request.form.to_dict())

    db = get_db()

    if request.form.get('Digits') == '#':
        record = db.audio.find_one({'sid': request.form['CallSid']})

        logger.info(
            'recording successful. duration: %ss',
            request.form['RecordingDuration'])

        # Reminder job has not been created yet so save in 'audio' for now

        db.audio.update_one(
          {'sid': request.form['CallSid']},
          {'$set': {
              'audio_url': request.form['RecordingUrl'],
              'audio_duration': request.form['RecordingDuration'],
              'status': 'recorded'
        }})

        smart_emit('record_audio', {
            'status': 'recorded',
            'audio_url': request.form['RecordingUrl']})

        voice = twiml.Response()
        voice.say('Message recorded. Goodbye.', voice='alice')
        voice.hangup()

        return voice

#-------------------------------------------------------------------------------
def on_complete():
    logger.debug('on_complete: %s', request.form.to_dict())

    db = get_db()

    r = db.audio.find_one({'sid': request.form['CallSid']})

    if r['status'] != 'recorded':
        smart_emit('record_audio', {
            'status': 'failed',
            'description': 'There was a problem recording your voice audio'})

    return True
