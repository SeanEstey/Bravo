from twilio import twiml
import os
import logging
from datetime import datetime,date,time,timedelta
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import request, current_app
from flask_login import current_user

from app import db
from .. import utils
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def dial():
    '''Request: POST from Bravo javascript client with 'To' arg
    Response: JSON dict {'status':'string'}
    '''
    agency = db['users'].find_one({'user': current_user.username})['agency']

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
            status_callback = '%s/notify/record/interact.xml' % os.environ.get('BRAVO_HTTP_HOST'),
            status_events = ["completed"],
            status_method = 'POST')
    except Exception as e:
        logger.error('call to %s failed. %s', request.form['To'], str(e))
        logger.debug('tb: ', exc_info=True)
    else:
        logger.info('%s call to %s', call.status, request.form['To'])
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


    logger.info('Dial status: %s', call.status)

    return call

#-------------------------------------------------------------------------------
def on_answer():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    logger.info('Sending record twimlo response to client')

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

    return voice

    #send_socket('record_audio', {'msg': 'Listen to the call for instructions'})

#-------------------------------------------------------------------------------
def on_interact():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    logger.debug('on_interact args: %s', request.form.to_dict())

    if request.form.get('Digits') == '#':
        record = db.audio.find_one({'sid': request.form['CallSid']})

        logger.info('Recording completed. Sending audio_url to client')

        # Reminder job has not been created yet so save in 'audio' for now

        db.audio.update_one(
          {'sid': request.form['CallSid']},
          {'$set': {
              'audio_url': request.form['RecordingUrl'],
              'audio_duration': request.form['RecordingDuration'],
              'status': 'completed'
        }})

        from app.socketio import socketio_app

        socketio_app.emit('record_audio', {'audio_url': request.form['RecordingUrl']})

        voice = twiml.Response()
        voice.say('Message recorded. Goodbye.', voice='alice')
        voice.hangup()

        return voice
