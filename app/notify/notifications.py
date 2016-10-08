import twilio
from flask import render_template
import logging
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
import requests
from pymongo.collection import ReturnDocument
from bson.objectid import ObjectId
import bson.json_util
import json
import re

# Import modules
from app import gsheets
from app import utils
from app import tasks
from app import etap

# Import objects
from app import app, db, socketio

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

    logger.info('notification type %s status %s sending',
            notification['type'], notification['status'])

    if notification['status'] != 'pending':
        return False

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

    if notification.get('attempts') >= app.config['MAX_CALL_ATTEMPTS']:
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
          url = app.config['PUB_URL'] + '/notify/voice/play/on_answer.xml',
          status_callback = app.config['PUB_URL'] + '/notify/voice/on_complete',
          status_method = 'POST',
          status_events = ["completed"],
          method = 'POST',
          if_machine = 'Continue'
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

    try:
        response = requests.post(
            app.config['LOCAL_URL'] + '/notify/render',
            json={
                "template": template['file'],
                "to": notification['to'],
                "account": utils.mongo_formatter(
                    db['accounts'].find_one({'_id':notification['acct_id']}),
                    to_local_time=True,
                    to_strftime="%A, %B %d",
                    bson_to_json=True),
                "evnt_id": str(notification['evnt_id'])
          })
    except requests.RequestException as e:
        logger.error('render_notification: %s. response: %s',
                str(e), response.json())
        return False

    mid = utils.send_email(
        notification['to'],
        template['subject'],
        response.text,
        mailgun_conf
    )

    if mid == False:
        status = 'failed'
    else:
        status = 'queued'

    db['emails'].insert({
        #'agency': job['agency'],
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
def _send_sms(notification, twilio_conf):
    '''Private method called by send()
    '''

    return True

#-------------------------------------------------------------------------------
def on_email_status(webhook):
    '''
    @webhook: webhook args POST'd by mailgun'''

    logger.info('notific email handler')

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
def rmv_msg(job_id, msg_id):
    n = db['reminders'].remove({'_id':ObjectId(msg_id)})

    db['jobs'].update(
        {'_id':ObjectId(job_id)},
        {'$inc':{'voice.count':-1}}
    )

    return n

#-------------------------------------------------------------------------------
def edit(notification_id, fields):
    '''User editing a notification value from GUI
    '''

    for fieldname, value in fields:
        if fieldname == 'event_dt':
          try:
            value = parse(value)
          except Exception, e:
            logger.error('Could not parse event_dt in /edit/call')
            return '400'

        logger.info('Editing ' + fieldname + ' to value: ' + str(value))

        #field = 'custom.'+fieldname

        db['reminders'].update(
            {'_id':ObjectId(reminder_id)},
            {'$set':{fieldname: value}}
        )

#-------------------------------------------------------------------------------
def get_voice(notific, template_file):
    '''Return rendered HMTL template as string
    Called from flask so has context
    @notification: mongodb dict document
    @template_key: name of content dict containing file path
    '''

    logger.debug('get_voice')

    account = db['accounts'].find_one({'_id':notific['acct_id']})

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
                action='/notify/voice/play/on_interact.xml',
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
          notific['content']['template']['default']['file']
        )

        voice.say(content, voice='alice')

        voice.gather(numDigits=1,
                    action='/notify/voice/play/on_interact.xml',
                    method='POST')
    # Digit 2: Cancel pickup
    elif args.get('Digits') == '2':
        tasks.cancel_pickup.apply_async(
            (str(notific['evnt_id']), str(notific['acct_id'])),
            queue=app.config['DB']
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
def call_event(args):
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

#-------------------------------------------------------------------------------
def create(job, schema, idx, buf_row, errors):
    '''Create a Reminder document in MongoDB from file input row.
    @job: MongoDB job record
    @schema: template dict from reminder_templates.json file
    @idx: .csv file row index (in case of error)
    @buf_row: array of values from csv file
    '''

    reminder = {
        "job_id": job['_id'],
        "agency": job['agency'],
        "voice": {
          "status": "pending",
          "attempts": 0,
        },
        "email": {
          "status": "pending"
        },
        "custom": {}
    }

    try:
        for i, field in enumerate(schema['import_fields']):
            db_field = field['db_field']

            # Format phone numbers
            if db_field == 'voice.to':
              buf_row[i] = strip_phone(buf_row[i])
            # Convert any date strings to datetime obj
            elif field['type'] == 'date':
                try:
                    local = pytz.timezone("Canada/Mountain")
                    buf_row[i] = parse(buf_row[i]).replace(tzinfo=pytz.utc).astimezone(local)
                except TypeError as e:
                    errors.append('Row %d: %s <b>Invalid Date</b><br>',
                                (idx+1), str(buf_row))

            if db_field.find('.') == -1:
                reminder[db_field] = buf_row[i]
            else:
                # dot notation means record is stored as sub-record
                parent = db_field[0 : db_field.find('.')]
                child = db_field[db_field.find('.')+1 : len(db_field)]
                reminder[parent][child] = buf_row[i]
        return reminder
    except Exception as e:
        logger.info('Error writing db reminder: %s', str(e))
        return False

#-------------------------------------------------------------------------------
def allowed_file(filename):
    return '.' in filename and \
     filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

