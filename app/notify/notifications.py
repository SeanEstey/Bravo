import twilio
from flask import render_template, current_app
import logging
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
import requests
from pymongo.collection import ReturnDocument
from bson.objectid import ObjectId
import bson.json_util
import json
import re

from .. import mailgun, gsheets, utils, etap
#from app import tasks

from app import db

logger = logging.getLogger(__name__)

#-------------------------------Stuff Todo---------------------------------------
# TODO: add sms template files
# TODO: include date in email subject

#-------------------------------------------------------------------------------
def insert(evnt_id, event_dt, trig_id, acct_id, _type, to, content):
    '''Add a notification tied to an event and trigger
    @evnt_id: _id of db.notific_events document
    @trig_id: _id of db.triggers document
    @acct_id: _id of db.accounts document
    @type: one of ['sms', 'voice', 'email']
    @to: phone number or email
    @content:
        'source': 'template/audio_url',
        'template': {'default':{'file':'path', 'subject':'email_sub'}}
        'audio_url': 'url'
    Returns:
      -id (ObjectId)
    '''

    return db['notifications'].insert_one({
        'evnt_id': evnt_id,
        'trig_id': trig_id,
        'acct_id': acct_id,
        'event_dt': event_dt,
        'status': 'pending',
        'attempts': 0,
        'to': to,
        'type': _type,
        'content': content,
        'opted_out': False
    }).inserted_id

#-------------------------------------------------------------------------------
def send(notification, agency_conf):
    '''TODO: store conf data for twilio or mailgun when created, not on
    send()
    '''

    if notification['status'] != 'pending':
        return False

    logger.debug('Sending %s', notification['type'])

    if notification['type'] == 'voice':
        return _send_call(notification, agency_conf['twilio'])
    elif notification['type'] == 'sms':
        return _send_sms(notification, agency_conf['twilio'])
    elif notification['type'] == 'email':
        return send_email(notification, agency_conf['mailgun'])

#-------------------------------------------------------------------------------
def _send_call(notification, twilio_conf):
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
def send_email(notification, mailgun_conf, key='default'):
    '''Private method called by send()
    @key = dict key in email schemas for which template to use
    '''

    template = notification['content']['template'][key]

    with current_app.test_request_context():
        current_app.config['SERVER_NAME'] = current_app.config['PUB_URL']
        try:
            body = render_template(
                template['file'],
                to = notification['to'],
                account = utils.mongo_formatter(
                    db['accounts'].find_one({'_id':notification['acct_id']}),
                    to_local_time=True,
                    to_strftime="%A, %B %d",
                    bson_to_json=True
                ),
                evnt_id = notification['evnt_id']
            )
        except Exception as e:
            logger.error('render email: %s ', str(e))
            current_app.config['SERVER_NAME'] = None
            return False
        current_app.config['SERVER_NAME'] = None

    mid = mailgun.send(
        notification['to'],
        template['subject'],
        body,
        mailgun_conf)

    if mid == False:
        status = 'failed'
    else:
        status = 'queued'

    agency = db['agencies'].find_one({'mailgun.domain': mailgun_conf['domain']})

    db['emails'].insert({
        'agency': agency['name'],
        'mid': mid,
        'status': status,
        'type': 'notification',
        'on_status': {}
    })

    db['notifications'].update_one(
        {'_id':notification['_id']},
        {'$set': {'status':status, 'mid': mid}})

    return mid

#-------------------------------------------------------------------------------
def on_email_status(webhook):
    '''
    @webhook: webhook args POST'd by mailgun'''

    db['notifications'].update_one(
      {'mid': webhook['Message-Id']},
      {'$set':{
        "status": webhook['event'],
        "code": webhook.get('code'),
        "reason": webhook.get('reason'),
        "error": webhook.get('error')
      }}
    )

#-------------------------------------------------------------------------------
def _send_sms(notification, twilio_conf):
    '''Private method called by send()
    '''
    return True

#-------------------------------------------------------------------------------
def rmv_msg(job_id, msg_id):
    n = db['reminders'].remove({'_id':ObjectId(msg_id)})

    db['jobs'].update(
        {'_id':ObjectId(job_id)},
        {'$inc':{'voice.count':-1}}
    )

    return n

#-------------------------------------------------------------------------------
def edit(acct_id, fields):
    '''User editing a notification value from GUI
    '''
    for fieldname, value in fields:
        if fieldname == 'udf.pickup_dt':
          try:
            value = parse(value)
          except Exception, e:
            logger.error('Could not parse event_dt in /edit/call')
            return '400'

        db['accounts'].update({'_id':acct_id}, {'$set':{fieldname:value}})

        # update notification 'to' fields if phone/email edited
        if fieldname == 'email':
            db['notifications'].update_one(
                {'acct_id':acct_id},
                {'$set':{'to':value}})
        elif fieldname == 'phone':
            db['notifications'].update_one(
                {'acct_id':acct_id, '$or': [{'type':'voice'},{'type':'sms'}]},
                {'$set': {'to':value}})

        logger.info('Editing ' + fieldname + ' to value: ' + str(value))

        return True


#-------------------------------------------------------------------------------
def get_voice(notific, template_file):
    '''Return rendered HMTL template as string
    Called from flask so has context
    @notification: mongodb dict document
    @template_key: name of content dict containing file path
    '''

    logger.debug('get_voice')

    account = db['accounts'].find_one({'_id':notific['acct_id']})

    with current_app.app_context():
        current_app.config['SERVER_NAME'] = current_app.config['PUB_URL']
        try:
            content = render_template(
                template_file,
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
            logger.error('get_voice: %s ', str(e))
            return 'Error'
        current_app.config['SERVER_NAME'] = None

    content = content.replace("\n", "")
    content = content.replace("  ", "")

    logger.debug('speak template: %s', content)

    db['notifications'].update_one({'_id':notific['_id']},{'$set':{'speak':content}})

    return content

#-------------------------------------------------------------------------------
def on_call_answered(args):
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

    # Html template content or audio url?

    if notific['content']['source'] == 'template':
        voice.say(
            get_voice(
                notific,
                notific['content']['template']['default']['file']),
            voice='alice'
        )
    elif notific['content']['source'] == 'audio_url':
        voice.play(notific['content']['audio_url'])
    else:
        logger.error('Unknown schema type!')
        voice.say("Error!", voice='alice')

    # Prompt user for action after voice audio plays
    voice.gather(numDigits=1,
                action=current_app.config['PUB_URL'] + '/notify/voice/play/interact.xml',
                method='POST')

    return voice

#-------------------------------------------------------------------------------
def on_call_interact(args):
    '''
    Return: twilio.twiml.Response
    '''

    logger.debug('voice_play_interact args: %s', args)

    notific = db['notifications'].find_one({'sid': args['CallSid']})

    if not notific:
        return False

    voice = twilio.twiml.Response()

    # Digit 1: Repeat message
    if args.get('Digits') == '1':
        content = get_voice(
          notific,
          notific['content']['template']['default']['file'])

        voice.say(content, voice='alice')

        voice.gather(
            numDigits=1,
            action=current_app.config['PUB_URL'] + '/notify/voice/play/interact.xml',
            method='POST')

    # Digit 2: Cancel pickup
    elif args.get('Digits') == '2':
        from .. import tasks
        tasks.cancel_pickup.apply_async(
            (str(notific['evnt_id']), str(notific['acct_id'])),
            queue=current_app.config['DB']
        )

        account = db['accounts'].find_one({'_id':notific['acct_id']})
        dt = utils.tz_utc_to_local(account['udf']['future_pickup_dt'])

        voice.say(
          'Thank you. Your next pickup will be on ' +\
          dt.strftime('%A, %B %d') + '. Goodbye',
          voice='alice'
        )
        voice.hangup()

    #elif job['schema']['type'] == 'announce_voice':
    #    if args.get('Digits') == '1':
    #        voice.play(job['audio_url'])
    #        voice.gather(numDigits=1, action='/reminders/voice/play/on_interact.xml', method='POST')

    return voice

#-------------------------------------------------------------------------------
def on_call_complete(args):
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
