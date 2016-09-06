import twilio.twiml
import logging
from datetime import datetime,date
from dateutil.parser import parse
import time
from werkzeug import secure_filename
import codecs
import os
import csv
import requests
from bson.objectid import ObjectId
import bson.json_util
import json
import re
import pytz
from pymongo import ReturnDocument
from flask.ext.login import current_user

from app import app, db, info_handler, error_handler, debug_handler, socketio
from tasks import celery_app
from gsheets import create_rfu
import utils
import etap
from scheduler import get_next_pickups

logger = logging.getLogger(__name__)
logger.addHandler(debug_handler)
logger.addHandler(info_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.DEBUG)

#-------------------------------------------------------------------------------
@celery_app.task
def monitor_jobs():
    '''Scheduler process. Runs via celerybeat every few minutes.
    Will finish off any active jobs and begin any pending scheduled jobs.
    '''

    monitor_pending_jobs()
    monitor_active_jobs()

#-------------------------------------------------------------------------------
def monitor_pending_jobs():
    '''Runs on celerybeat schedule with frequency defined in config.py.
    Starts pending jobs as scheduled. Returns # pending jobs'''

    pending = db['jobs'].find({'status': 'pending'})

    in_progress = db['jobs'].find({'status': 'in-progress'})

    status = {}

    for job in pending:
        if datetime.utcnow() < job['voice']['fire_at']:
            print('Job_ID %s: Pending in %s' %
            (str(job['_id']), str(job['voice']['fire_at'] - datetime.utcnow())))
            status[job['_id']] = 'pending'
            continue

        if in_progress.count() > 0:
            logger.info('Another job in-progress. Waiting to begin Job_ID %s',
                        str(job['_id']))
            status[job['_id']] = 'waiting'
            continue

        # Start new job
        db['jobs'].update_one(
          {'_id': job['_id']},
          {'$set': {
            "status": "in-progress",
            "voice.started_at": datetime.utcnow()}})

        logger.info('Job_ID %s: Sending calls', job['_id'])

        status[job['_id']] = 'in-progress'

        #requests.get(LOCAL_URL + '/sendsocket', params={
        #  'name': 'update_job',
        #  'data': json.dumps({'id': str(job['_id']), 'status':'in-progress'})
        #})

        # May not be able to start celery task from inside another.
        # Make a server request to /reminders/<job_id>/execute if this doesn't
        # work
        send_calls.apply_async((str(job['_id']).encode('utf-8'),),queue=app.config['DB'])

    if datetime.utcnow().minute == 0:
        logger.info('%d pending jobs', pending.count())

    return status

#-------------------------------------------------------------------------------
def monitor_active_jobs():
    '''Runs on celerybeat schedule with frequency defined in config.py.
    Monitors active jobs to do any redials, mark them as complete, or
    kill any hung jobs.
    Returns list of statuses'''

    in_progress = db['jobs'].find({'status': 'in-progress'})

    status = {}

    for job in in_progress:
        now = datetime.utcnow()

        if (now - job['voice']['started_at']).seconds > app.config['JOB_TIME_LIMIT']:
            # The celery process will have already killed the worker task if
            # it hung, but we'll catch the error here and clean up.

            logger.error('Job_ID %s: Ran over time limit! Celery task should '+ \
                         'have been killed automatically.', str(job['_id']))

            logger.error('Job_ID %s dump: %s', str(job['_id']), job)

            db['jobs'].update_one(
                {'_id':job['_id']},
                {'$set': {'status': 'failed'}})

            status[job['_id']] = 'failed'

            continue

        # Job is active. Do nothing.
        if db['reminders'].find({
          'job_id': job['_id'],
          '$or':[
            {'voice.status': 'pending'},
            {'voice.status': 'queued'},
            {'voice.status': 'ringing'},
            {'voice.status': 'in-progress'}
        ]}).count() > 0:
            status[job['_id']] = 'in-progress'
            continue

        print('Job_ID %s: Active' % ((str(job['_id']))))

        # Any needing redial?
        incompletes = db['reminders'].find({
          'job_id': job['_id'],
          'voice.attempts': {'$lt': app.config['MAX_CALL_ATTEMPTS']},
          '$or':[
            {'voice.status': 'busy'},
            {'voice.status': 'no-answer'}]})

        if incompletes.count() == 0:
            # Job Complete!
            db['jobs'].update_one(
              {'_id': job['_id']},
              {'$set': { 'status': 'completed'}})

            logger.info('Job_ID %s: Completed', str(job['_id']))

            status[job['_id']] = 'completed'

            # Connect back to server and notify
            requests.get(app.config['LOCAL_URL'] + '/complete/' + str(job['_id']))

            #email_job_summary(job['_id'])

        else:
            logger.info('Job ID %s: Redialing %d incompletes', str(job['_id']), incompletes.count())

            status[job['_id']] = 'redialing'

            # Redial busy or no-answer incompletes
            # This should be a new celery worker task
            send_calls.apply_async((str(job['_id']).encode('utf-8'),), queue=app.config['DB'])

    return status

#-------------------------------------------------------------------------------
@celery_app.task
def send_calls(job_id):
    '''job_id: str of BSON.ObjectID
    Returns number of calls fired
    '''

    # Default call order is alphabetically by name
    reminders = db['reminders'].find({'job_id': ObjectId(job_id)}).sort('name',1)
    agency = db['jobs'].find_one({'_id':ObjectId(job_id)})['agency']
    twilio = db['agencies'].find_one({'name':agency})['twilio']

    calls_fired = 0

    # Fire all calls
    for reminder in reminders:
        # TODO: change voice.status to "cancelled" on no_pickup request,
        # eliminate this test
        if 'no_pickup' in reminder['custom']:
            continue

        if reminder['voice']['status'] not in ['pending', 'no-answer', 'busy']:
            continue

        if reminder['voice']['attempts'] >= app.config['MAX_CALL_ATTEMPTS']:
            continue

        if not reminder['voice']['to']:
            db['reminders'].update_one(
              {'_id': reminder['_id']},
              {'$set': {
                  'voice.status': 'no_number'
              }})
            continue

        call = dial(reminder['voice']['to'], twilio['ph'], twilio['keys']['main'])

        if isinstance(call, Exception):
            logger.info('%s failed (%d: %s)',
                        reminder['voice']['to'], call.code, call.msg)

            db['reminders'].update_one(
              {'_id':reminder['_id']},
              {'$set': {
                "voice.status": "failed",
                "voice.error": call.msg,
                "voice.code": call.code}})
        else:
            logger.info('%s %s', reminder['voice']['to'], call.status)

            calls_fired += 1

            db['reminders'].update_one(
              {'_id':reminder['_id']},
              {'$set': {
                "voice.status": call.status,
                "voice.sid": call.sid,
                "voice.attempts": reminder['voice']['attempts']+1}})

    # TODO: Add back in socket.io

    #r['id'] = str(reminder['_id'])
    #payload = {'name': 'update_call', 'data': json.dumps(r)}
    #requests.get(LOCAL_URL+'/sendsocket', params=payload)

    logger.info('Job_ID %s: %d calls fired', job_id, calls_fired)

    return calls_fired

#-------------------------------------------------------------------------------
@celery_app.task
def send_emails(job_id):
    job_id = ObjectId(job_id)

    job = db['jobs'].find_one({'_id':job_id})
    reminders = db['reminders'].find({'job_id':job_id})

    emails_sent = 0

    for reminder in reminders:
        if 'email' not in reminder:
            continue

        if reminder['email']['status'] != 'pending':
            continue

        if not reminder['email']['recipient']:
            db['reminders'].update_one(
                {'_id':reminder['_id']},
                {'$set': {'email.status': 'no_email'}}
            )
            continue

        #send_socket('update_msg', {'id':str(msg['_id']), 'email_status': 'no_email'})

        try:
            data = reminder['custom']
            local = pytz.timezone("Canada/Mountain")
            data['event_date'] = reminder['event_date'].replace(tzinfo=pytz.utc).astimezone(local)
            data['account'] = {
              "name": reminder['name'],
              "email": reminder['email']['recipient']
            }
            # Need this for email/send view
            data['from'] = {'reminder_id': str(reminder['_id'])}

            data['cancel_pickup_url'] = app.config['PUB_URL'] + '/reminders/' + str(job['_id']) + '/' + str(reminder['_id']) + '/cancel_pickup'

            json_args = bson_to_json({
              "agency": job['agency'],
              "recipient": reminder['email']['recipient'],
              "template": job['schema']['email']['reminder']['file'],
              "subject": job['schema']['email']['reminder']['subject'],
              "data": data
            })

            headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

            r = requests.post(app.config['LOCAL_URL'] + '/email/send', headers=headers, data=json_args)

            db['reminders'].update_one(
                {'_id':reminder['_id']},
                {'$set': {'email.mid': r.text}})

        except requests.exceptions.RequestException as e:
            logger.error('Error sending email: %s', str(e))
        else:
            emails_sent += 1
            logger.debug(r.text)

    '''TODO: Add date into subject
    #subject = 'Reminder: Upcoming event on  ' +
    # reminder['imported']['event_date'].strftime('%A, %B %d')
    '''

    logger.info('Job_ID %s: %d emails sent', str(job_id), emails_sent)

    return emails_sent

#-------------------------------------------------------------------------------
def get_jobs(args):
    '''Display jobs for agency associated with current_user
    If no 'n' specified, display records (sorted by date) {1 .. JOBS_PER_PAGE}
    If 'n' arg, display records {n .. n+JOBS_PER_PAGE}
    Returns: list of job dict objects
    '''

    agency = db['users'].find_one({'user': current_user.username})['agency']

    jobs = db['jobs'].find({'agency':agency})

    if jobs:
        jobs = jobs.sort('fire_calls_dtime',-1).limit(app.config['JOBS_PER_PAGE'])

    # Convert naive UTC datetime objects to local
    local = pytz.timezone("Canada/Mountain")

    # Convert to list so we don't exhaust the cursor by modifying and
    # can return iterable list
    jobs = list(jobs)

    for job in jobs:
        fire_dt = job['voice']['fire_at']
        local_fire_dt = fire_dt.replace(tzinfo=pytz.utc).astimezone(local)
        job['voice']['fire_at'] = local_fire_dt

    return jobs

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
def rmv_msg(job_id, msg_id):
    n = db['reminders'].remove({'_id':ObjectId(msg_id)})

    db['jobs'].update(
        {'_id':ObjectId(job_id)},
        {'$inc':{'voice.count':-1}}
    )

    return n

#-------------------------------------------------------------------------------
def reset_job(job_id):
    n = db['reminders'].update(
      {'job_id': ObjectId(job_id)},
      {'$set': {
        'voice.status': 'pending',
        'voice.attempts': 0,
        'email.status': 'pending'
    },
    '$unset': {
        'custom.no_pickup': '',
        'voice.sid': '',
        'voice.answered_by': '',
        'voice.ended_at': '',
        'voice.speak': '',
        'voice.code': '',
        'voice.duration': '',
        'voice.error': '',
        'email.error': '',
        'email.reason': '',
        'email.code': ''
        }
    },
    multi=True)

    logger.info('%s reminders reset', n['nModified'])

    n = db['jobs'].update(
      {'_id': ObjectId(job_id)}, {
        '$set': {
            'status': 'pending',
        },
        '$unset': {
            'voice.started_at': '',
            'email.started_at': ''
        }
    })

    logger.info('%s jobs reset', n['nModified'])

#-------------------------------------------------------------------------------
def edit_msg(reminder_id, fields):
    '''User editing a reminder value from GUI
    '''

    for fieldname, value in fields:
        if fieldname == 'event_date':
          try:
            value = parse(value)
          except Exception, e:
            logger.error('Could not parse event_date in /edit/call')
            return '400'

        logger.info('Editing ' + fieldname + ' to value: ' + str(value))

        #field = 'custom.'+fieldname

        db['reminders'].update(
            {'_id':ObjectId(reminder_id)},
            {'$set':{fieldname: value}}
        )

#-------------------------------------------------------------------------------
def dial(to, from_, twilio_keys):
    '''Returns twilio call object'''

    if to[0:2] != "+1":
        to = "+1" + to

    try:
        twilio_client = twilio.rest.TwilioRestClient(
          twilio_keys['sid'],
          twilio_keys['auth_id']
        )


        call = twilio_client.calls.create(
          from_ = from_,
          to = to,
          url = app.config['PUB_URL'] + '/reminders/call.xml',
          status_callback = app.config['PUB_URL'] + '/reminders/call_event',
          status_method = 'POST',
          status_events = ["completed"], # adding more status events adds cost
          method = 'POST',
          if_machine = 'Continue'
        )

        logger.debug(vars(call))

    except twilio.TwilioRestException as e:
        logger.error(e)

        if not e.msg:
            if e.code == 21216:
                e.msg = 'not_in_service'
            elif e.code == 21211:
                e.msg = 'no_number'
            elif e.code == 13224:
                e.msg = 'invalid_number'
            elif e.code == 13223:
                e.msg = 'invalid_number_format'
            else:
                e.msg = 'unknown_error'
        return e

    return call

#-------------------------------------------------------------------------------
def get_voice_response(args):
    '''Returns a twilio.twiml.Response object if voice recording,
    returns a .html template file for rendering by view otherwise
    '''

    if 'msg' in args or 'Digits' in args:
        return get_resp_xml_template(args)
    else:
        return get_answer_xml_template(args)

#-------------------------------------------------------------------------------
def get_resp_xml_template(args):
    '''Twilio TwiML Voice Request. User has made interaction with call.
    @args: dict of flask request.form
    Returns: either twilio.twiml.Response obj or .html template
    '''

    logger.debug('get_resp_xml: CallSid %s', args['CallSid'])

    reminder = db['reminders'].find_one({'voice.sid': args.get('CallSid')})
    job = db['jobs'].find_one({'_id': reminder['job_id']})

    response = twilio.twiml.Response()

    # Voice recording?
    if reminder is None:

        record = db['audio'].find_one({'sid': args['CallSid']})

        if not record:
            logger.error('Unknown SID %s (reminders.get_answer_xml)',
                        args['CallSid'])
            return response

        if args['Digits']:
            digits = args['Digits']
            logger.info('recordaudio digit='+digits)

            if digits == '#':
                logger.info('Recording completed. Sending audio_url to client')

                recording_info = {
                  'audio_url': args['RecordingUrl'],
                  'audio_duration': args['RecordingDuration'],
                  'sid': args['CallSid'],
                  'call_status': args['CallStatus']
                }

                db['audio'].update_one(
                  {'sid': args['CallSid']},
                  {'$set': recording_info})

                socketio.emit('record_audio', recording_info)
                response = twilio.twiml.Response()
                response.say('Message recorded', voice='alice')

                return Response(str(response), mimetype='text/xml')
        else:
            logger.info('recordaudio: no digits')

        return True

    # Repeat message request...
    if args.get('Digits') == '1':
        try:
            # Simplest case: announce_voice template. Play audio file
            if job['schema']['type'] == 'announce_voice':
                # TODO: Fixme
                response = twilio.twiml.Response()
                response.play(job['audio_url'])
                return response

            return job['schema']['voice']['reminder']['file']
        except Exception as e:
            logger.error('Error generating xml response: %s', str(e))
            return False
    # Cancel Pickup special request...
    elif args.get('Digits') == '2':
        cancel_pickup.apply_async((str(reminder['_id']),), queue=app.config['DB'])

        local = pytz.timezone("Canada/Mountain")
        response.say(
          'Thank you. Your next pickup will be on ' +\
          reminder['custom']['next_pickup'].replace(tzinfo=pytz.utc).astimezone(local).strftime('%A, %B %d') + '. Goodbye',
          voice='alice')

        return response

#-------------------------------------------------------------------------------
def get_answer_xml_template(args):
    '''TwiML Voice Request
    Call has been answered (by machine or human)
    Returns either twilio.twiml.Response obj or .html template
    '''

    logger.info('%s %s (%s)', args['To'], args['CallStatus'], args.get('AnsweredBy'))
    logger.debug('get_answer_xml: CallSid %s', args['CallSid'])

    reminder = db['reminders'].find_one_and_update(
      {'voice.sid': args['CallSid']},
      {'$set': {
        "voice.status": args['CallStatus'],
        "voice.answered_by": args.get('AnsweredBy')}},
      return_document=ReturnDocument.AFTER)

    if reminder:
        # send_socket('update_msg',
        # {'id': str(msg['_id']), 'call_status': msg['call]['status']})
        job = db['jobs'].find_one({'_id': reminder['job_id']})
        try:
            # Simplest case: announce_voice template. Play audio file
            if job['schema']['type'] == 'announce_voice':
                # TODO: Fixme
                response = twilio.twiml.Response()
                response.play(job['audio_url'])
                return response

            return job['schema']['voice']['reminder']['file']
        except Exception as e:
            logger.error('reminders.get_answer_xml_template', exc_info=True)
            return False

    # Not a reminder. Maybe a special msg recording?
    if reminder is None:
        record = db['audio'].find_one({'sid': args['CallSid']})

        response_xml = twilio.twiml.Response()

        if not record:
            logger.error('Unknown SID %s (reminders.get_answer_xml)',
                        args['CallSid'])
            return response_xml

        logger.info('Sending record twimlo response to client')

        # Record voice message
        response_xml.say(
            'Record your message after the beep. Press pound when complete.',
            voice='alice'
        )
        response_xml.record(
            method= 'GET',
            action= app.config['PUB_URL'] + '/reminders.call.xml',
            playBeep= True,
            finishOnKey='#'
        )
        #send_socket('record_audio', {'msg': 'Listen to the call for instructions'})

        return response_xml

#-------------------------------------------------------------------------------
def call_event(args):
    '''Callback handler called by Twilio on 'completed' event (more events can
    be specified, at $0.00001 per event). Updates status of event in DB.
    Returns: 'OK' string to twilio if no problems.
    '''

    logger.debug('call_event args: %s', args)

    if args['CallStatus'] == 'completed':
        reminder = db['reminders'].find_one_and_update(
          {'voice.sid': args['CallSid']},
          {'$set': {
            "voice.status": args['CallStatus'],
            "voice.ended_at": datetime.now(),
            "voice.duration": args['CallDuration'],
            "voice.answered_by": args.get('AnsweredBy')
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
def email_job_summary(job_id):
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)

    job = db['jobs'].find_one({'_id':job_id})

    try:
        r = requests.post(app.config['LOCAL_URL'] + '/email/send', data=json.dumps({
          "recipient": app.config['FROM_EMAIL'],
          "template": 'email/job_summary.html',
          "subject": 'Job Summary %s' % job['name'],
          "data": {
            "summary": {
              "answered": db['reminders'].find({
                'job_id':job_id, 'voice.answered_by':'human'}).count(),
              "voicemail": db['reminders'].find({
                'job_id':job_id, 'voice.answered_by':'machine'}).count(),
              "no_answer" : db['reminders'].find({
                'job_id':job_id, 'voice.status':'no-answer'}).count(),
              "busy": db['reminders'].find({
                'job_id':job_id, 'voice.status':'busy'}).count(),
              "failed" : db['reminders'].find({
                'job_id':job_id, 'voice.status':'failed'}).count()
            },
            "fails": db['reminders'].find(
              {'job_id':job_id,
               '$or': [
                 {"email.status" : "bounced"},
                 {"email.status" : "dropped"},
                 {"voice.status" : "failed"}
               ]
              },
              {'custom': 1, 'email.error': 1, 'voice.error':1,
               'voice.code':1, 'email.status': 1, '_id': 0})
          }
        }))

        logger.info('Email report sent')
    except Exception as e:
        logger.error('Error sending job_summary email: %s', str(e))

#-------------------------------------------------------------------------------
@celery_app.task
def cancel_pickup(reminder_id):
    '''Update users eTapestry account with next pickup date and send user
    confirmation email
    @reminder_id: string form of ObjectId
    Returns: True if no errors, False otherwise
    '''
    logger.info('Cancelling pickup for \'%s\'', reminder_id)

    reminder = db['reminders'].find_one({'_id':ObjectId(reminder_id)})

    # Outdated/in-progress or deleted job?
    if not reminder:
        logger.error('No pickup request fail. Invalid reminder_id \'%s\'', reminder_id)
        return False

    # Already cancelled?
    if 'no_pickup' in reminder['custom']:
        if reminder['custom']['no_pickup'] == True:
            logger.info('No pickup already processed for account %s', reminder['account_id'])
            return False

    # No next pickup date?
    if 'next_pickup' not in reminder['custom']:
        logger.error("Next Pickup for reminder_msg _id %s is missing.", str(reminder['_id']))
        return False

    job = db['jobs'].find_one({'_id':reminder['job_id']})

    local = pytz.timezone("Canada/Mountain")
    no_pickup = 'No Pickup ' + reminder['event_date'].replace(tzinfo=pytz.utc).astimezone(local).strftime('%A, %B %d')

    db['reminders'].update(
      {'_id':reminder['_id']},
      {'$set': {
        "voice.status": "cancelled",
        "custom.office_notes": no_pickup,
        "custom.no_pickup": True
      }}
    )
    # send_socket('update_msg', {
    #  'id': str(msg['_id']),
    #  'office_notes':no_pickup
    #  })

    job = db['jobs'].find_one({'_id':reminder['job_id']})
    settings = db['agencies'].find_one({'name':job['agency']})
    keys = {'user':settings['etapestry']['user'], 'pw':settings['etapestry']['pw'],
            'agency':job['agency'],'endpoint':app.config['ETAPESTRY_ENDPOINT']}

    try:
        # Write to eTapestry
        etap.call('no_pickup', keys, {
          "account": reminder['account_id'],
          "date": reminder['event_date'].strftime('%d/%m/%Y'),
          "next_pickup": reminder['custom']['next_pickup'].strftime('%d/%m/%Y')
        })
    except Exception as e:
        logger.error("Error writing to eTap: %s", str(e))

    # Send email w/ next pickup
    if 'next_pickup' in reminder['custom']:
        local = pytz.timezone("Canada/Mountain")
        next_pickup = reminder['custom']['next_pickup'].replace(tzinfo=pytz.utc).astimezone(local).strftime('%A, %B %d')
        data = {
          "agency": job['agency'],
          "recipient": reminder['email']['recipient'],
          "template": job['schema']['email']['no_pickup']['file'],
          "subject": job['schema']['email']['no_pickup']['subject'],
          "data": {
            "name": reminder['name'],
            "from": reminder['email']['recipient'],
            "next_pickup": next_pickup,
            "account": {
              "email": reminder['email']['recipient']
            }
          }
        }

        try:
            requests.post(
              app.config['LOCAL_URL'] + '/email/send', json=data)

            logger.info('Emailed Next Pickup to %s', reminder['email']['recipient'])
        except Exception as e:
            logger.error("Error sending no_pickup followup email: %s", str(e))
            return False

    return True

#-------------------------------------------------------------------------------
@celery_app.task
def set_no_pickup(url, params):
    r = requests.get(url, params=params)

    if r.status_code != 200:
        logger.error('etap script "%s" failed. status_code:%i', url, r.status_code)
        return r.status_code

    logger.info('No pickup for account %s', params['account'])

    return r.status_code

#-------------------------------------------------------------------------------
def parse_csv(csvfile, import_fields):
    '''Checks the .csv file buffer for correct headers/rows
    csvfile: buffer from opened .csv file
    returns: buffer of rows on success, error str on failure
    import_fields: list of header column mappings from json schema
    '''

    reader = csv.reader(csvfile, dialect=csv.excel, delimiter=',', quotechar='"')
    buffer = []
    header_err = False

    try:
        for row in reader:
            # Test header row
            if reader.line_num == 1:
                if len(row) != len(import_fields):
                    header_err = True
                else:
                    for col in range(0, len(row)):
                      if row[col] != import_fields[col]['file_header']:
                          header_err = True
                          break

                if header_err:
                    columns = []
                    for element in import_fields:
                        columns.append(element['file_header'])

                    logger.error('Invalid header row. Missing columns: %s', str(columns))

                    return 'Your file is missing the proper header rows:<br> \
                    <b>' + str(columns) + '</b><br><br>' \
                    'Here is your header row:<br><b>' + str(row) + '</b><br><br>' \
                    'Please fix your mess and try again.'

            # Skip over empty Row 2 in eTapestry export files
            elif reader.line_num == 2:
                continue
            # Read each line from file into buffer
            else:
                if len(row) != len(import_fields):
                    return 'Line #' + str(line_num) + ' has ' + str(len(row)) + \
                    ' columns. Look at your mess:<br><br><b>' + str(row) + '</b>'
                else:
                    buffer.append(row)
    except Exception as e:
        logger.error('reminders.parse_csv: %s', str(e))
        return False

    return buffer

#-------------------------------------------------------------------------------
def record_audio(args, agency):
    '''Used to initiate voice recording reminder.
    1. User POST request to /reminders/recordaudio->this function->Dial
    user->Success response
    2. User answers->Twilio POST request to /reminders/call.xml->Record XML
    response
    3. User ends recording, hits '#'->Twilio GET request to /reminders/call.xml->Recording
    saved->Confirmation XML response
    '''

    if method == 'POST':
        logger.info('Record audio request from ' + args['To'])

        twilio = db['agencies'].find_one({'name':agency})

        r = dial(args['To'], twilio['ph'], twilio['keys']['main'])

        logger.info('Dial response=' + json.dumps(r))

        if r['call_status'] == 'queued':
            db['audio'].insert(r)
            del r['_id']

        return flask.json.jsonify(r)

    return 'OK'

#-------------------------------------------------------------------------------
def job_print(job_id):
    if isinstance(job_id, str):
        job_id = ObjectId(job_id)

    job = db['jobs'].find_one({'_id':job_id})

    if 'ended_at' in job:
        time_elapsed = (job['voice']['ended_at'] - job['voice']['started_at']).total_seconds()
    else:
        time_elapsed = ''

    summary = {
        "totals": {
          "completed": {
            'answered': db['reminders'].find(
                {'job_id':job_id, 'voice.answered_by':'human'}).count(),
            'voicemail': db['reminders'].find(
                {'job_id':job_id, 'voice.answered_by':'machine'}).count()
          },
          "no-answer" : db['reminders'].find(
              {'job_id':job_id, 'voice.status':'no-answer'}).count(),
          "busy": db['reminders'].find(
              {'job_id':job_id, 'voice.status':'busy'}).count(),
          "failed" : db['reminders'].find(
              {'job_id':job_id, 'voice.status':'failed'}).count(),
          "time_elapsed": time_elapsed
        },
        "calls": list(db['reminders'].find(
            {'job_id':job_id},{'voice.ended_at':0, 'job_id':0}))
    }

    return summary

#-------------------------------------------------------------------------------
def allowed_file(filename):
    return '.' in filename and \
     filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

#-------------------------------------------------------------------------------
def cancel_job(job_id):
    n = db['jobs'].remove({'_id':ObjectId(job_id)})

    if n is None:
        logger.error('Could not remove job %s', job_id)

    db['reminders'].remove({'job_id':ObjectId(job_id)})

    logger.info('Removed Job [ID %s]', str(job_id))

#-------------------------------------------------------------------------------
def submit_job(form, file):
    '''POST request to create new job from new_job.html template'''
    logger.debug('new job form: %s', str(form))

    # A. Validate file
    try:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file_path = app.config['UPLOAD_FOLDER'] + '/' + filename
        else:
            logger.error('could not save file')

            return {'status':'error',
                    'title': 'Filename Problem',
                    'msg':'Could not save file'}
    except Exception as e:
        logger.error(str(e))

        return {
          'status':'error',
          'title':'file problem',
          'msg':'could not upload file'
        }

    agency = db['users'].find_one({'user': current_user.username})['agency']

    # B. Get schema definitions from json file
    try:
        with open('templates/schemas/'+agency+'.json') as json_file:
          schemas = json.load(json_file)['reminders']
    except Exception as e:
        logger.error(str(e))
        return {'status':'error',
                'title': 'Problem Reading reminder_templates.json File',
                'msg':'Could not parse file: ' + str(e)}

    schema = ''
    for s in schemas:
        if s['name'] == form['template_name']:
            schema = s
            break

    # C. Open and parse submitted .CSV file
    try:
        with codecs.open(file_path, 'r', 'utf-8-sig') as f:
            buffer = parse_csv(f, schema['import_fields'])

            if type(buffer) == str:
                return {
                  'status':'error',
                  'title': 'Problem Reading File',
                  'msg':buffer
                }

            logger.info('Parsed %d rows from %s', len(buffer), filename)
    except Exception as e:
        logger.error('submit_job: parse_csv: %s', str(e))

        return {'status':'error',
                'title': 'Problem Reading File',
                'msg':'Could not parse .CSV file: ' + str(e)}

    if not form['job_name']:
        job_name = filename.split('.')[0].replace('_',' ')
    else:
        job_name = form['job_name']

    try:
        fire_calls_dtime = parse(form['date'] + ' ' + form['time'])
    except Exception as e:
        logger.error(str(e))

        return {
          'status':'error',
          'title': 'Invalid Date',
          'msg':'Could not parse the schedule date you entered: ' + str(e)
        }

    # D. Create mongo 'job' and 'reminder' records
    job = {
        'name': job_name,
        'agency': agency,
        'schema': schema,
        'voice': {
            'fire_at': fire_calls_dtime,
            'count': len(buffer)
        },
        'status': 'pending'
    }

    # Special cases
    if form['template_name'] == 'announce_voice':
        job['audio_url'] = form['audio-url']
    elif form['template_name'] == 'announce_text':
        job['message'] = form['message']

    #logger.debug('new job dump: %s', json.dumps(job))

    job_id = db['jobs'].insert(job)
    job['_id'] = job_id

    try:
        errors = []
        reminders = []

        for idx, row in enumerate(buffer):
            msg = create(job, schema, idx, row, errors)

            if msg:
                reminders.append(msg)

            if len(errors) > 0:
                e = 'The file <b>' + filename + '</b> has some errors:<br><br>'
                for error in errors:
                    e += error
                    db['jobs'].remove({'_id':job_id})

                return {'status':'error', 'title':'File Format Problem', 'msg':e}

        db['reminders'].insert(reminders)

        logger.info('[%s] Job "%s" Created [ID %s]', agency, job_name, str(job_id))

        # Special case
        #if form['template_name'] == 'etw':
        get_next_pickups.apply_async((str(job['_id']), ), queue=app.config['DB'])

        banner_msg = 'Job \'' + job_name + '\' successfully created! '\
                + str(len(reminders)) + ' messages imported.'

        return {'status':'success', 'msg':banner_msg}

    except Exception as e:
        logger.error(str(e))

        return {'status':'error', 'title':'error', 'msg':str(e)}

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
