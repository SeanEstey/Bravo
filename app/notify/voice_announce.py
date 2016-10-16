'''app.notify.voice_announce'''

import twilio
import os

def on_call_interact(notific, args):
    if args.get('Digits') == '1':
        voice = twilio.twiml.Response()

        voice.play(notific['on_answer']['audio_url'], voice='alice')

        voice.gather(
            numDigits=1,
            action="%s/notify/voice/play/interact.xml" % os.environ.get('BRAVO_HTTP_HOST'),
            method='POST')

        return voice
