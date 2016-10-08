from twilio import twiml
import logging
from datetime import datetime,date,time,timedelta
from flask import request

# Import objects
from app import app, db, socketio

logger = logging.getLogger(__name__)

def dial(args):
    '''Request: POST from Bravo javascript client with 'To' arg
    Response: JSON dict {'status':'string'}
    '''
    agency = db['users'].find_one({'user': current_user.username})['agency']

    logger.info('Record audio request from ' + request.form['To'])

    twilio = db['agencies'].find_one({'name':agency})['twilio']

    # FIXME
    call = None
    '''reminders.dial(
      request.form['To'],
      twilio['ph'],
      twilio['keys']['main'],
      app.config['PUB_URL'] + '/voice/record/on_answer.xml'
    )'''

    logger.info('Dial status: %s', call.status)

    if call.status == 'queued':
        doc = {
            'date': datetime.utcnow(),
            'sid': call.sid,
            'agency': agency,
            'to': call.to,
            'from': call.from_,
            'status': call.status,
            'direction': call.direction
        }

        db['audio'].insert_one(doc)

    return call

def on_answer(args):
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
        action= app.config['PUB_URL'] + '/voice/record/on_complete.xml',
        playBeep= True,
        finishOnKey='#'
    )

    #send_socket('record_audio', {'msg': 'Listen to the call for instructions'})

def on_complete(args):
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    logger.debug('/voice/record_on_complete.xml args: %s',
      request.form.to_dict())

    if request.form.get('Digits') == '#':
        record = db['audio'].find_one({'sid': request.form['CallSid']})

        logger.info('Recording completed. Sending audio_url to client')

        # Reminder job has not been created yet so save in 'audio' for now

        db['audio'].update_one(
          {'sid': request.form['CallSid']},
          {'$set': {
              'audio_url': request.form['RecordingUrl'],
              'audio_duration': request.form['RecordingDuration'],
              'status': 'completed'
        }})

        socketio.emit('record_audio', {'audio_url': request.form['RecordingUrl']})

        voice = twiml.Response()
        voice.say('Message recorded. Goodbye.', voice='alice')
        voice.hangup()