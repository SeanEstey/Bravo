'''app.notify.recording'''
import os
from datetime import datetime
from twilio.rest import TwilioRestClient
from twilio import TwilioRestException, twiml
from flask import g, request
from app.lib.utils import print_vars
from app.lib.loggy import Loggy
from .. import smart_emit
log = Loggy('notify.record')

#-------------------------------------------------------------------------------
def dial_recording():
    '''Request: POST from Bravo javascript client with 'To' arg
    Response: JSON dict {'status':'string'}
    '''

    agency = g.db['users'].find_one({'user': g.user.user_id})['agency']

    log.info('Record audio request from ' + request.form['To'])

    twilio = g.db['agencies'].find_one({'name':agency})['twilio']

    try:
        client = TwilioRestClient(twilio['api']['sid'], twilio['api']['auth_id'])
    except TwilioRestException as e:
        log.error('twilio REST error. %s', str(e))
        log.debug('tb: ', exc_info=True)
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
            status_events = ["completed"],
            status_method = 'POST')
    except Exception as e:
        log.error('call to %s failed. %s', request.form['To'], str(e))
        return {'status':'failed', 'description': 'Invalid phone number'}
    else:
        log.debug(print_vars(call))

        g.db.audio.insert_one({
            'date': datetime.utcnow(),
            'sid': call.sid,
            'agency': agency,
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
    voice = twiml.Response()
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

    smart_emit('record_audio', {'status':'answered'})

    return voice

#-------------------------------------------------------------------------------
def on_interact():
    '''Request: Twilio POST
    Response: twilio.twiml.Response with voice content
    '''

    #log.debug('on_interact: %s', request.form.to_dict())

    if request.form.get('Digits') == '#':
        record = g.db.audio.find_one({'sid': request.form['CallSid']})

        log.info(
            'recording successful. duration: %ss',
            request.form['RecordingDuration'], group=record['agency'])

        # Reminder job has not been created yet so save in 'audio' for now

        g.db.audio.update_one(
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
    log.debug('on_complete: %s', request.form.to_dict())

    r = g.db.audio.find_one({'sid': request.form['CallSid']})

    if r['status'] != 'recorded':
        smart_emit('record_audio', {
            'status': 'failed',
            'description': 'There was a problem recording your voice audio'})

    return True
