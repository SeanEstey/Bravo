'''notify.voice'''

'''{
    (...),
    "on_answer" : {
        "source" : "template",
        "path" : "voice/vec/reminder.html"
    },
    "on_interact": {
        "module": "pickup_service",
        "func": "on_call_interact"
    },
    "tracking": {
        "attempts": 0,
        "duration": 13,
        "
        "ended_dt": "ISODate(...)",
        "sid": "49959jfd93jd"
    },
    "to" : "(403) 874-9467",
    "type" : "voice"
}'''

#-------------------------------------------------------------------------------
def add(evnt_id, event_dt, trig_id, acct_id, to, on_answer, on_interact):
    return db['notifics'].insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': event_dt,
        'status': 'pending',
        'on_answer': on_answer,
        'on_interact': on_interact,
        'to': to,
        'type': 'voice',
        'opted_out': False
        'tracking': {
            'sid': None,
            'duration': None,
            'answered_by': None,
            'attempts': 0
        }
    }).inserted_id


#-------------------------------------------------------------------------------
def call(notification, twilio_conf):
    '''Private method called by send()
    '''

    if notification.get('attempts') >= 2: #current_app.config['MAX_CALL_ATTEMPTS']:
        return False

    if notification['to'][0:2] != "+1":
        to = "+1" + notification['to']

    try:
        client = twilio.rest.TwilioRestClient(
          twilio_conf['keys']['main']['sid'],
          twilio_conf['keys']['main']['auth_id']
        )

        call = client.calls.create(
          from_ = twilio_conf['ph'],
          to = to,
          url = current_app.config['PUB_URL'] + '/notify/voice/play/answer.xml',
          method = 'POST',
          if_machine = 'Continue',
          status_callback = current_app.config['PUB_URL'] + '/notify/voice/complete',
          status_method = 'POST',
          status_events = ["completed"],
          fallback_url = current_app.config['PUB_URL'] + '/notify/voice/fallback',
          fallback_method = 'POST'
        )
    except twilio.TwilioRestException as e:
        logger.error(e)

    logger.debug(vars(call))

    db['notifications'].update_one(
        {'_id': notification['_id']}, {
        '$set': {
            'status': call.status,
            'sid': call.sid or None
        },
        '$inc': {'attempts':1}
    })

    logger.info('Call %s for %s', call.status, notification['to'])

    if call.status != 'queued':
        return False
    else:
        return True

#-------------------------------------------------------------------------------
def get_speak(notific, template_file):
    '''Return rendered HMTL template as string
    Called from flask so has context
    @notification: mongodb dict document
    @template_key: name of content dict containing file path
    '''

    account = db['accounts'].find_one({'_id':notific['acct_id']})

    with current_app.app_context():
        current_app.config['SERVER_NAME'] = current_app.config['PUB_URL']
        try:
            content = render_template(
                template_file,
                medium='voice',
                account = utils.mongo_formatter(
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

    db['notifications'].update_one({'_id':notific['_id']},{'$set':{'speak':content}})

    return content

#-------------------------------------------------------------------------------
def on_answer(args):
    '''User answered call. Get voice content.
    Return: twilio.twiml.Response
    '''

    logger.debug('voice_play_answer args: %s', args)

    logger.info('%s %s (%s)',
      args['To'], args['CallStatus'], args.get('AnsweredBy')
    )

    notific = db['notifications'].find_one_and_update(
      {'sid': args['CallSid']},
      {'$set': {
        "status": args['CallStatus'],
        "answered_by": args.get('AnsweredBy')}},
      return_document=ReturnDocument.AFTER)

    # send_socket('update_msg',
    # {'id': str(msg['_id']), 'call_status': msg['call]['status']})

    voice = twilio.twiml.Response()


    # TODO: replace "content" key with "on_answer" for notification dicts

    # Html template content or audio url?

    if notific['on_answer']['source'] == 'template':
        voice.say(
            get_speak(
                db['accounts'].find_one({'_id':notific['acct_id']}),
                notific,
                notific['on_answer']['template']['default']['file']),
            voice='alice'
        )
    elif notific['on_answer']['source'] == 'audio_url':
        voice.play(notific['on_answer']['audio_url'])
    else:
        logger.error('Unknown schema type!')
        voice.say("Error!", voice='alice')

    # All voice templates prompt key "1" to repeat message
    voice.gather(numDigits=1,
                action=current_app.config['PUB_URL'] + '/notify/voice/play/interact.xml',
                method='POST')

    return voice

#-------------------------------------------------------------------------------
def on_interact(args):
    '''The user has entered input. Invoke handler function to get response.
    Returns: twilio.twiml.Response
    '''

    logger.debug('voice_play_interact args: %s', args)

    notific = db['notifications'].find_one({'sid': args['CallSid']})

    if not notific:
        return False

    '''Notification dict defines:
          "on_interact": {
                "module": "pickup_service",
                "func": "on_call_interact"
            },
    '''

    # Import assigned handler module and invoke the function

    module = __import__(notific['on_interact']['module'])
    handler_func = getattr(module, notific['on_interact']['func']
    voice = handler_func(notific, args)

    return voice

#-------------------------------------------------------------------------------
def on_complete(args):
    '''Callback handler called by Twilio on 'completed' event (more events can
    be specified, at $0.00001 per event). Updates status of event in DB.
    Returns: 'OK' string to twilio if no problems.
    '''

    logger.debug('call_event args: %s', args)

    if args['CallStatus'] == 'completed':
        reminder = db['notifications'].find_one_and_update(
          {'sid': args['CallSid']},
          {'$set': {
            'status': args['CallStatus'],
            'ended_at': datetime.now(),
            'duration': args['CallDuration'],
            'answered_by': args.get('AnsweredBy')
          }},
          return_document=ReturnDocument.AFTER)
    else:
        reminder = db['notifications'].find_one_and_update(
          {'sid': args['CallSid']},
          {'$set': {
            "code": args.get('SipResponseCode'), # in case of failure
            "status": args['CallStatus']
          }},
          return_document=ReturnDocument.AFTER)

    if args['CallStatus'] == 'failed':
        logger.error(
          '%s %s (%s)',
          args['To'], args['CallStatus'], args.get('SipResponseCode'))

        msg = ('Account {a} error {e} calling {to}').format(a=reminder['account_id'],
            e=args['SipResponseCode'], to=args['To'])

        # TODO: Change to reminder['agency'] after Aug 1 calls
        #create_rfu.apply_async(
        #  args=(job['agency'], msg),
        #  queue=app.config['DB'])

    # Call completed without error
    elif args['CallStatus'] == 'completed':
        logger.info('%s %s (%s, %ss)',
          args['To'], args['CallStatus'], args['AnsweredBy'], args['CallDuration'])
    else:
        logger.info('%s %s', args['To'], args['CallStatus'])

    if reminder:
        return 'OK'

    # If no Mongo reminder record returned, this call might be an audio recording call
    if reminder is None:
        audio = db['audio'].find_one({'sid': args['CallSid']})

        if audio:
            logger.info('Record audio call complete')

            db['audio'].update(
                {'sid':args['CallSid']},
              {'$set': {"status": args['CallStatus']}
            })
        else:
            logger.error('Unknown SID %s (reminders.call_event)', args['CallSid'])

    return 'OK'

#-------------------------------------------------------------------------------
def strip_phone(to):
    if not to:
        return ''
    return to.replace(' ', '').replace('(','').replace(')','').replace('-','')
