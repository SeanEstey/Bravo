
def on_call_interact(notific, args):
    if args.get('Digits') == '1':
        voice = twilio.twiml.Response()

        voice.play(notific['on_answer']['audio_url'], voice='alice')

        voice.gather(
            numDigits=1,
            action="%s/notify/voice/play/interact.xml" % current_app.config['PUB_URL'],
            method='POST')

        return voice
