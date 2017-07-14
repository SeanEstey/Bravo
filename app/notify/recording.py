'''app.notify.recording'''
import os
from datetime import datetime
from twilio.rest import Client
from twilio import twiml
from flask import g, request
from app.lib.utils import obj_vars
#from .. import smart_emit
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def dial_recording():
    '''Request: POST from Bravo javascript client with 'To' arg
    Response: JSON dict {'status':'string'}
    '''

    #agency = g.db['users'].find_one({'user': g.user.user_id})['agency']

    log.info('Record audio request from ' + request.form['To'])

    twilio = g.db['groups'].find_one({'name':g.group})['twilio']

    try:
        client = Client(twilio['api']['sid'], twilio['api']['auth_id'])
    except Exception as e:
        log.exception('twilio REST error. %s', e.message)
        return 'failed'

    call = None
    host = os.environ.get('BRV_HTTP_HOST')
    if host.find('https') == 0:
        host = host.replace('https', 'http')

    try:
        call = client.calls.create(
            from_ = twilio['voice']['number'],
            to = request.form['To'],
            url ='%s/notify/record/answer.xml' % host,
            method = 'POST',
            if_machine = 'Continue',
            fallback_url = '%s/notify/voice/fallback' % host,
            fallback_method = 'POST',
            status_callback = '%s/notify/record/complete' % host,
            status_callback_event = "completed",
            status_callback_method = 'POST')
    except Exception as e:
        log.error('call to %s failed. %s', request.form['To'], str(e))
        return {'status':'failed', 'description': 'Invalid phone number'}
    else:
        log.debug(obj_vars(call))

        g.db.audio.insert_one({
            'date': datetime.utcnow(),
            'sid': call.sid,
            'agency': g.group,
            'to': call.to,
            'from': call.from_,
            'status': call.status,
            'direction': call.direction
        })


    return {'call_status':call.status}

#-------------------------------------------------------------------------------
def on_answer():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    host = os.environ.get('BRV_HTTP_HOST')
    if host.find('https') == 0:
        host = host.replace('https', 'http')
    # Record voice message
    from twilio.twiml.voice_response import VoiceResponse
    voice = VoiceResponse()
    voice.say('Record your message after the beep. Press pound when complete.',
      voice='alice'
    )
    voice.record(
        method= 'POST',
        action= '%s/notify/record/interact.xml' % host,
        playBeep= True,
        finishOnKey='#',
        timeout=120
    )

    #smart_emit('record_audio', {'status':'answered'})

    return voice

#-------------------------------------------------------------------------------
def on_interact():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    if request.form.get('Digits') == '#':
        record = g.db.audio.find_one({'sid': request.form['CallSid']})
        g.group = record['agency']

        log.info('recording done. duration: %ss', request.form['RecordingDuration'])

        # Reminder job has not been created yet so save in 'audio' for now

        g.db.audio.update_one(
          {'sid': request.form['CallSid']},
          {'$set': {
              'audio_url': request.form['RecordingUrl'],
              'audio_duration': request.form['RecordingDuration'],
              'status': 'recorded'
        }})

        from app.main.socketio import smart_emit
        smart_emit('record_audio', {
            'status': 'recorded',
            'audio_url': request.form['RecordingUrl']})

        from twilio.twiml.voice_response import VoiceResponse
        voice = VoiceResponse()
        voice.say('Message recorded. Goodbye.', voice='alice')
        voice.hangup()

        return voice

#-------------------------------------------------------------------------------
def on_complete():

    #log.debug('on_complete: %s', request.form.to_dict())

    r = g.db.audio.find_one({'sid': request.form['CallSid']})

    if r['status'] != 'recorded':
        pass
        #smart_emit('record_audio', {
        #    'status': 'failed',
        #    'description': 'There was a problem recording your voice audio'})

    return True
