import twilio
import logging
from datetime import datetime,date,time,timedelta
from dateutil.parser import parse
import requests
from pymongo.collection import ReturnDocument
from bson.objectid import ObjectId
import bson.json_util
import json
import re

from app import app, db, info_handler, error_handler, debug_handler, socketio
from tasks import celery_app
from gsheets import create_rfu
import utils
import etap
#from scheduler import add_future_pickups

logger = logging.getLogger(__name__)
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)


#-------------------------------Stuff Todo---------------------------------------
# TODO: update all needed reminder['voice'] with reminder['voice']['conf']
# TODO: add sms template files
# TODO: include date in email subject
# TODO: write general add_job and add_reminder functions

#-------------------------------------------------------------------------------
def add(event_id, trig_id, _type, to, account, udf, content):
    '''Add a notification tied to an event and trigger
    @type: one of ['sms', 'voice', 'email']
    @content:
        'source': 'template/audio_url',
        'template': {'default':{'file':'path', 'subject':'email_sub'}}
        'audio_url': 'url'
    Returns:
      -id (ObjectId)
    '''

    db['notifications'].insert_one({
        'event_id': event_id,
        'trig_id': trig_id,
        'status': 'pending',
        'to': to,
        'type': _type,
        'account': {
            'name': account['name'],
            'id': account['id'],
            'udf': udf
        },
        'content': content
    })

#-------------------------------------------------------------------------------
def send_voice_call(notification, twilio_conf):
    if notification.get('attempts') >= app.config['MAX_CALL_ATTEMPTS']:
        return False

    if notification['to'][0:2] != "+1":
        to = "+1" + to

    try:
        twilio_client = twilio.rest.TwilioRestClient(
          twilio_conf['keys']['main']['sid'],
          twilio_conf['keys']['main']['auth_id']
        )

        call = twilio_client.calls.create(
          from_ = twilio['ph'],
          to = to,
          url = app.config['PUB_URL'] + '/reminders/voice/play/on_answer.xml',
          status_callback = app.config['PUB_URL'] + '/reminders/voice/on_complete',
          status_method = 'POST',
          status_events = ["completed"],
          method = 'POST',
          if_machine = 'Continue'
        )
    except twilio.TwilioRestException as e:
        logger.error(e)

    logger.debug(vars(call))

    db['notifications'].update_one(notification, {
        '$set': {
            'status': call.status,
            'sid': call.sid or None,
            'code': call.code or None,
            'error': call.error or None
        },
        '$inc': {'attempts':1}
    })

    logger.info('Call %s for %s', call.status, notification['to'])

#-------------------------------------------------------------------------------
def send_email(notification, mailgun_conf, key='default'):
    '''
    @key = dict key in email schemas for which template to use
    '''

    body = utils.render_html(
        notification['content']['template']['email'][key]['file'],
        data = {
            'to': notification['to'],
            'event_dt': utils.utc_to_local(notification['event_dt']),
            'account': notification['account'],
        })

    mid = utils.send_email(
        reminder['email']['conf']['recipient'],
        reminder['email']['conf']['subject'],
        body,
        mailgun_conf
    )

    db['emails'].insert({
        'agency': job['agency'],
        'mid': json.loads(r.text)['id'],
        'status': 'queued',
        'type': 'reminder',
        'on_status': {
            'command': 'update',
            'target': 'db',
            '_id': reminder['_id']
        }})

    db['reminders'].update_one(
        {'_id':reminder['_id']},
        {'$set': {'email.mid': mid}})

#-------------------------------------------------------------------------------
def send_sms(notification, twilio_conf):
    return True
    
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
def get_voice_content(notification, template_key):
    '''Return rendered HMTL template as string
    @notification: mongodb dict document
    @template_key: name of content dict containing file path
    '''

    # Go through all UDFs and convert UTC datetimes to local
    for key, val in notificaton['account']['udf'].iteritems():
        if isinstance(val, datetime):
            notification['account']['udf'][key] = utils.utc_to_local(val)

    content = utils.render_html(
      notificaton['content']['template'][template_key]['file'],
      notification=json.loads(bson_to_json(notification))
    )

    content = content.replace("\n", "")
    content = content.replace("  ", "")

    logger.debug('speak template: %s', content)

    db['notifications'].update_one({'_id':notification['_id']},{'$set':{'speak':content}})

    return content

#-------------------------------------------------------------------------------
def get_voice_play_answer_response(args):
    '''User answered call. Get voice content.
    Return: twilio.twiml.Response
    '''

    logger.debug('voice_play_answer args: %s', args)

    logger.info('%s %s (%s)',
      args['To'], args['CallStatus'], args.get('AnsweredBy')
    )

    reminder = db['notifications'].find_one_and_update(
      {'sid': args['CallSid']},
      {'$set': {
        "status": args['CallStatus'],
        "answered_by": args.get('AnsweredBy')}},
      return_document=ReturnDocument.AFTER)

    # send_socket('update_msg',
    # {'id': str(msg['_id']), 'call_status': msg['call]['status']})

    voice = twilio.twiml.Response()

    # Html template content or audio url?
    
    if notification['content']['source'] == 'template':
        content = get_voice_content(
            notification, 
            notification['content']['template']['default']['file']
        )
        
        voice.say(content, voice='alice')
    elif notification['content']['source'] == 'audio_url':
        voice.play(notification['content']['audio_url'])
    else:
        logger.error('Unknown schema type!')
        voice.say("Error!", voice='alice')

    # Prompt user for action after voice audio plays
    voice.gather(numDigits=1, action='/reminders/voice/play/on_interact.xml', method='POST')

    return voice

#-------------------------------------------------------------------------------
def get_voice_play_interact_response(args):
    '''
    Return: twilio.twiml.Response
    '''

    logger.debug('voice_play_interact args: %s', args)

    reminder = db['reminders'].find_one({'voice.sid': args['CallSid']})
    job = db['jobs'].find_one({'_id': reminder['job_id']})

    voice = twilio.twiml.Response()

    # TODO: replace job['schema']['type'] with reminder['voice']['from_source']

    if job['schema']['type'] == 'reminder':

        # Digit 1: Repeat message
        if args.get('Digits') == '1':
            content = get_voice_content(
              reminder,
              job['schema']['voice']['reminder']['file']
            )

            voice.say(content, voice='alice')
            voice.gather(numDigits=1, action='/reminders/voice/play/on_interact.xml', method='POST')

        # Digit 2: Cancel pickup
        elif args.get('Digits') == '2':
            cancel_pickup.apply_async((str(reminder['_id']),), queue=app.config['DB'])

            dt = reminder['custom']['future_pickup_dt']
            dt = dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Canada/Mountain'))

            voice.say(
              'Thank you. Your next pickup will be on ' +\
              dt.strftime('%A, %B %d') + '. Goodbye',
              voice='alice'
            )
            voice.hangup()

    elif job['schema']['type'] == 'announce_voice':
        if args.get('Digits') == '1':
            voice.play(job['audio_url'])
            voice.gather(numDigits=1, action='/reminders/voice/play/on_interact.xml', method='POST')

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
        reminder = db['reminders'].find_one_and_update(
          {'voice.sid': args['CallSid']},
          {'$set': {
            "voice.code": args.get('SipResponseCode'), # in case of failure
            "voice.status": args['CallStatus']
          }},
          return_document=ReturnDocument.AFTER)

    if args['CallStatus'] == 'failed':
        logger.error(
          '%s %s (%s)',
          args['To'], args['CallStatus'], args.get('SipResponseCode'))

        # TODO: Remove this line after Aug 1st reminders. agency will be stored
        # in each reminder record. no need to
        job = db['jobs'].find_one({'_id': reminder['job_id']})

        msg = ('Account {a} error {e} calling {to}').format(a=reminder['account_id'],
            e=args['SipResponseCode'], to=args['To'])

        # TODO: Change to reminder['agency'] after Aug 1 calls
        create_rfu.apply_async(
          args=(job['agency'], msg),
          queue=app.config['DB'])

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

            db['audio'].update({
              'sid':args['CallSid']},
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

#-------------------------------------------------------------------------------
def bson_to_json(a):
    '''Convert mongoDB BSON format to JSON.
    Converts timestamps to formatted date strings
    '''

    try:
        a = bson.json_util.dumps(a)

        for group in re.findall(r"\{\"\$date\": [0-9]{13}\}", a):
            timestamp = json.loads(group)['$date']/1000
            date_str = '"' + datetime.fromtimestamp(timestamp).strftime('%A, %B %d') + '"'
            a = a.replace(group, date_str)
    except Exception as e:
        logger.error('bson_to_json: %s', str(e))
        return False

    return a
