import twilio
from twilio import twimlc
from bson import Binary, Code, json_util
from bson.objectid import ObjectId
import flask
from flask import Flask,render_template,request,g,Response,redirect,url_for
from datetime import datetime,date
from dateutil.parser import parse
import werkzeug
from werkzeug import secure_filename
import codecs
import os
import csv
from bson import Binary, Code, json_util
from bson.objectid import ObjectId

from app import celery_app, db, logger, login_manager, socketio
import utils
from config import *

#-------------------------------------------------------------------------------
def get_jobs(args):
  # If no 'n' specified, display records (sorted by date) {1 .. JOBS_PER_PAGE}
  # If 'n' arg, display records {n .. n+JOBS_PER_PAGE}
  if 'n' in args:
    jobs = db['reminder_jobs'].find().sort('fire_dtime',-1)
    jobs.skip(int(args['n'])).limit(JOBS_PER_PAGE);
  else:
    jobs = db['reminder_jobs'].find().sort('fire_dtime',-1).limit(JOBS_PER_PAGE)
    
  return jobs

#-------------------------------------------------------------------------------
@celery_app.task
def check_jobs():
  pending_jobs = db['jobs'].find({'status': 'pending'})
  
  #print(str(pending_jobs.count()) + ' pending jobs:')

  job_num = 1
  for job in pending_jobs:
    if datetime.now() > job['fire_dtime']:
      logger.info('Scheduler: Starting Job...')
      send_calls.apply_async((str(job['_id']), ), queue=DB_NAME)
    else:
      next_job_delay = job['fire_dtime'] - datetime.now()
      print '{0}): {1} starts in {2}'.format(job_num, job['name'], str(next_job_delay))
    job_num += 1
  
  in_progress_jobs = db['jobs'].find({'status': 'in-progress'})
  #print(str(in_progress_jobs.count()) + ' active jobs:')
  
  job_num = 1
  
  #for job in in_progress_jobs:
  #  print('    ' + str(job_num) + '): ' + job['name'])

  return pending_jobs.count()

#-------------------------------------------------------------------------------
@celery_app.task
def send_calls(job_id):
  try:
    job_id = ObjectId(job_id)
    job = db['jobs'].find_one({'_id':job_id})
    # Default call order is alphabetically by name
    messages = db['msgs'].find({'job_id':job_id}).sort('name',1)
    logger.info('\n\nStarting Job %s [ID %s]', job['name'], str(job_id))
    db['reminder_jobs'].update(
      {'_id': job['_id']},
      {'$set': {
        'status': 'in-progress',
        'started_at': datetime.now()
        }
      }
    )
    payload = {'name': 'update_job', 'data': json.dumps({'id':str(job['_id']), 'status':'in-progress'})}
    requests.get(LOCAL_URL+'/sendsocket', params=payload)
    # Fire all calls
    for msg in messages:
      if 'no_pickup' in msg:
        continue
      if msg['call_status'] != 'pending':
        continue
      r = dial(msg['imported']['to'])
      if r['call_status'] == 'failed':
        logger.info('%s %s (%d: %s)', msg['imported']['to'], r['call_status'], r['error_code'], r['call_error'])
      else: 
        logger.info('%s %s', msg['imported']['to'], r['call_status'])
      r['attempts'] = msg['attempts']+1
      db['msgs'].update(
        {'_id':msg['_id']},
        {'$set': r}
      )
      r['id'] = str(msg['_id'])
      payload = {'name': 'update_call', 'data': json.dumps(r)}
      requests.get(LOCAL_URL+'/sendsocket', params=payload)
    
    logger.info('Job Calls Fired.')
    r = requests.get(PUB_URL + '/' + str(job_id) + '/monitor')
    return 'OK'

  except Exception, e:
    logger.error('send_calls job_id %s', str(job_id), exc_info=True)

#-------------------------------------------------------------------------------
@celery_app.task
def send_emails(job_id):
 try:
    job_id = job_id.encode('utf-8')
    job = db['reminder_jobs'].find_one({'_id':ObjectId(job_id)})
    reminder_msgs = db['reminder_msgs'].find({'job_id':ObjectId(job_id)})
    emails = []
    
    for msg in reminder_msgs:
      if msg['email']['status'] != 'pending':
        continue
      
      if not msg['email']['recipient']:
        db['reminder_msgs'].update(
          {'_id':msg['_id']}, 
          {'$set': {'email_status': 'no_email'}}
        )
        continue
        #send_socket('update_msg', {'id':str(msg['_id']), 'email_status': 'no_email'})
      
      r = requests.post(PUB_URL + '/email/send', data=json.dumps({
        "recipient": msg['email']['recipient'],
        "template": job['template']['email_template'],
        "subject": job['template']['email_subject'],
        "name": msg['name'],
        "args": msg['custom']
      }))
      
      TODO: Add date into subject
      #subject = 'Reminder: Upcoming event on  ' + msg['imported']['event_date'].strftime('%A, %B %d')

    return 'OK'
  except Exception, e:
    logger.error('reminders.send_emails()', exc_info=True)

#-------------------------------------------------------------------------------
@celery_app.task
def monitor_calls(job_id):
  try:
    logger.info('Tasks: Monitoring Job')
    job_id = ObjectId(job_id)
    job = db['jobs'].find_one({'_id':job_id})

    # Loop until no incomplete calls remaining (all either failed or complete)
    while True:
      # Any calls still active?
      actives = db['msgs'].find({
        'job_id': job_id,
        '$or':[
          {'call_status': 'queued'},
          {'call_status': 'ringing'},
          {'call_status': 'in-progress'}
        ]
      })
      # Any needing redial?
      incompletes = db['msgs'].find({
        'job_id':job_id,
        'attempts': {'$lt': MAX_ATTEMPTS}, 
        '$or':[
          {'call_status': 'busy'},
          {'call_status': 'no-answer'}
        ]
      })
      
      # Job Complete!
      if actives.count() == 0 and incompletes.count() == 0:
        db['jobs'].update(
          {'_id': job_id},
          {'$set': {
            'status': 'completed',
            'ended_at': datetime.now()
            }
        })
        logger.info('\nCompleted Job %s [ID %s]\n', job['name'], str(job_id))
        # Connect back to server and notify
        requests.get(PUB_URL + '/complete/' + str(job_id))
        
        return 'OK'
      # Job still in progress. Any incomplete calls need redialing?
      elif actives.count() == 0 and incompletes.count() > 0:
        logger.info('Pausing %dsec then Re-attempting %d Incompletes.', REDIAL_DELAY, incompletes.count())
        time.sleep(REDIAL_DELAY)
        for call in incompletes:
          r = dial(call['imported']['to'])
          logger.info('%s %s', call['imported']['to'], r['call_status'])
          r['attempts'] = call['attempts']+1
          db['msgs'].update(
            {'_id':call['_id']},
            {'$set': r}
          )
      # Still active calls going out  
      else:
        time.sleep(10)
    # End loop
    return 'OK'
  except Exception, e:
    logger.error('monitor_calls job_id %s', str(job_id), exc_info=True)

#-------------------------------------------------------------------------------
# Create mongodb "reminder_msg" record from .CSV line
# job_id: mongo "job_reminder" record_id in ObjectId format
# template_def: template dict from reminder_templates.json file
# buf_row: array of values from csv file
# line_index: file row index (for error tracking)
def create_msg(job_id, template_def, line_index, buf_row, errors):
  msg = {
    "job_id": job_id,
    "call": {
      "status": "pending"
      "attempts": 0,
    },
    "email": {
      "status": "pending"
    },
    "custom": {}
  }

  for i, field in enumerate(template_def['import_fields']):
    db_field = field['db_field']
    
    # Format phone numbers
    if db_field == 'call.to':
      buf_row[i] = strip_phone(buf_row[i])
    # Convert any date strings to datetime obj
    elif field['type'] == 'date':
      try:
        buf_row[i] = parse(buf_row[i])
      except TypeError as e:
        errors.append('Row '+str(idx+1)+ ': ' + str(buf_row) + ' <b>Invalid Date</b><br>')
    
    if db_field.find('.') == -1:
      msg[db_field] = buf_row[i]
    # dot notation means record is stored as sub-record
    else:
      parent = db_field[0 : db_field.find('.')]
      child = db_field[db_field.find('.')+1 : len(db_field)]
      msg[parent][child] = buf_row[i]
   
  return msg

#-------------------------------------------------------------------------------
def rmv_msg(job_id, msg_id):
  db['reminder_msgs'].remove({'_id':ObjectId(msg_id)})
   
  db['reminder_jobs'].update(
    {'_id':ObjectId(job_id)}, 
    {'$inc':{'num_calls':-1}}
  )
 
#------------------------------------------------------------------------------- 
def edit_msg(job_id, msg_id, fields): 
  for fieldname, value in fields:
    if fieldname == 'event_date':
      try:
        value = parse(value)
      except Exception, e:
        logger.error('Could not parse event_date in /edit/call')
        return '400'
    logger.info('Editing ' + fieldname + ' to value: ' + str(value))
    field = 'imported.'+fieldname
    db['reminder_msgs'].update(
        {'_id':ObjectId(sid)}, 
        {'$set':{field: value}}
    )

#-------------------------------------------------------------------------------
def dial(to):
  try:
    twilio_client = twilio.rest.TwilioRestClient(
      TWILIO_ACCOUNT_SID, 
      TWILIO_AUTH_ID
    )
    call = twilio_client.calls.create(
      from_ = FROM_NUMBER,
      to = '+1'+to,
      url = PUB_URL + '/reminders/call_action',
      status_callback = PUB_URL + '/reminders/call_ended',
      status_method = 'POST',
      method = 'POST',
      if_machine = 'Continue'
    )

    return {'sid':call.sid, 'call_status':call.status}
  except twilio.TwilioRestException as e:
    if e.code == 21216:
      error_msg = 'not_in_service'
    elif e.code == 21211:
      error_msg = 'no_number'
    elif e.code == 13224:
      error_msg = 'invalid_number'
    elif e.code == 13223:
      error_msg = 'invalid_number_format'
    else:
      error_msg = e.message
    return {'sid':'', 'call_status': 'failed', 'error_code': e.code, 'call_error':error_msg}
  except Exception as e:
    logger.error('twilio.dial exception %s', str(e), exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
# Twilio callback handler. User has either answered call or made an interaction
# request_method: ['POST','GET']
# args: dictionary
def call_action(request_method, args):
  try:
    if request_method == 'POST':
      sid = args['CallSid']
      call_status = args['CallStatus']
      to = args['To']
      answered_by = args.get('AnsweredBy')
      
      logger.info('%s %s (%s)', to, call_status, answered_by)
      
      call = db['reminder_msgs'].find_one({'sid': args['CallSid']})

      if not call:
        # Might be special msg voice record call
        record = db['bravo'].find_one({'sid': args['CallSid']})
        if record:
          logger.info('Sending record twimlo response to client')
          # Record voice message
          response = twilio.twiml.Response()
          response.say('Record your message after the beep. Press pound when complete.', voice='alice')
          response.record(
            method= 'GET',
            action= PUB_URL+'/recordaudio',
            playBeep= True,
            finishOnKey='#'
          )
          send_socket('record_audio', {'msg': 'Listen to the call for instructions'}) 
          return Response(str(response), mimetype='text/xml')

      else:
        db['reminder_msgs'].update(
          {'sid':sid},
          {'$set': {'call_status':call_status}}
        )
        call = db['reminder_msgs'].find_one({'sid':sid})
        send_socket(
          'update_msg', {
            'id': str(call['_id']),
            'call_status': call_status
          }
        )
        job = db['reminder_jobs'].find_one({'_id':call['job_id']})
        
        return get_speak(job, call, answered_by)
     
    elif request_method == "GET":
      sid = form.get('CallSid')
      msg = db['reminder_msgs'].find_one({'sid':sid})
      job = db['reminder_jobs'].find_one({'_id':call['job_id']})
      digits = form.get('Digits')
      # Repeat Msg
      if digits == '1':
        return get_speak(job, msg, 'human')
      # Special Action (defined by template)
      elif digits == '2' and 'no_pickup' not in msg:
        no_pickup = 'No Pickup ' + msg['imported']['event_date'].strftime('%A, %B %d')
        db['reminder_msgs'].update(
          {'sid':sid},
          {'$set': {'imported.office_notes': no_pickup}}
        )
        send_socket('update_msg', {
          'id': str(call['_id']),
          'office_notes':no_pickup
          })
        # Write to eTapestry
        if 'account' in msg['imported']:
          url = 'http://bravovoice.ca/etap/etap.php'
          params = {
            'func': 'no_pickup', 
            'account': msg['imported']['account'], 
            'date':  msg['imported']['event_date'].strftime('%d/%m/%Y'),
            'next_pickup': msg['next_pickup'].strftime('%d/%m/%Y')
          }
          tasks.no_pickup_etapestry.apply_async((url, params, ), queue=DB_NAME)

        if msg['next_pickup']:
          response = twilio.twiml.Response()
          next_pickup_str = msg['next_pickup'].strftime('%A, %B %d')
          response.say('Thank you. Your next pickup will be on ' + next_pickup_str + '. Goodbye', voice='alice')
          return Response(str(response), mimetype='text/xml')

    response = twilio.twiml.Response()
    response.say('Goodbye', voice='alice')
  except Exception, e:
    logger.error('reminders.answer_call', exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
# Twilio callback handler. 
# args['CallStatus'] either: 'completed', 'failed', 'no-answer', or 'busy'
def call_ended(args):
  logger.info('%s %s', args['to'], args['CallStatus'])
    
  try:
    msg = db['reminder_msgs'].find_one({'sid':args['CallSid']})

    # Might be an audio recording call
    if not msg:
      audio = db['audio_msg'].find_one({'sid':args['CallSid']})
      if audio:
        logger.info('Record audio call complete')
        db['audio_msg'].update({'sid':args['CallSid']}, {'$set': {"status": args['CallStatus']}})
      return 'OK'
    
    # Is a reminder call
    
    fields = {
      "call.status": args['CallStatus'],
      "call.ended_at": datetime.now(),
      "call.duration": args['CallDuration'],
      "call.answered_by": args.get('AnsweredBy'),
      "call.error_code": args.get('SipResponseCode') # in case of failure
    }
    
    db['reminder_msgs'].update(
      {'sid':args['CallSid']},
      {'$set': fields}
    )
    
    #fields['id'] = str(call['_id'])
    #fields['attempts'] = call['attempts']
    #send_socket('update_msg', fields)
    
    return 'OK'
  except Exception, e:
    logger.error('%s update_call_status args: ' % args, exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
def sms(to, msg):
  try:
    twilio_client = twilio.rest.TwilioRestClient(
      TWILIO_ACCOUNT_SID, 
      TWILIO_AUTH_ID
    )
    message = twilio_client.messages.create(
      body = msg,
      to = '+1' + to,
      from_ = SMS_NUMBER,
      status_callback = PUB_URL + '/sms/status'
    )

    return {'sid': message.sid, 'call_status': message.status}

  except twilio.TwilioRestException as e:
    if e.code == 14101: 
      #"To" Attribute is Invalid
      error_msg = 'number_not_mobile'
    elif e.code == 30006:
      erorr_msg = 'landline_unreachable'
    else:
      error_msg = e.message

    return {'sid':'', 'call_status': 'failed', 'error_code': e.code, 'call_error':error_msg}

  except Exception as e:
    logger.error('sms exception %s', str(e), exc_info=True)

    return False

#-------------------------------------------------------------------------------
def strip_phone(to):
  if not to:
    return ''
  return to.replace(' ', '').replace('(','').replace(')','').replace('-','')

#-------------------------------------------------------------------------------
def get_speak(job, msg, answered_by, medium='voice'):
  # Simplest case: announce_voice template. Play audio file
  if job['template'] == 'announce_voice':
    response = twilio.twiml.Response()
    response.play(job['audio_url'])
    return Response(str(response), mimetype='text/xml')

  if 'event_date' in msg['imported']:
    try:
      date_str = msg['imported']['event_date'].strftime('%A, %B %d')
    except TypeError:
      logger.error('Invalid date in get_speak: ' + str(msg['imported']['event_date']))
      return False

  response = twilio.twiml.Response()
  response.say(speak, voice='alice')
  db['msgs'].update({'_id':msg['_id']},{'$set':{'speak':speak}})

  if speak.find(repeat_voice) >= 0:
    response.gather(
      action= PUB_URL + '/call/answer',
      method='GET',
      numDigits=1
    )
  return Response(str(response), mimetype='text/xml')

#-------------------------------------------------------------------------------
def send_email_report(job_id):
  try:
    if isinstance(job_id, str):
      job_id = ObjectId(job_id)
    
    job = db['jobs'].find_one({'_id':job_id})

    summary = {
      '<b>Summary</b>': {
        'Answered': db['msgs'].find({'job_id':job_id, 'answered_by':'human'}).count(),
        'Voicemail': db['msgs'].find({'job_id':job_id, 'answered_by':'machine'}).count(),
        'No-answer' : db['msgs'].find({'job_id':job_id, 'call_status':'no-answer'}).count(),
        'Busy': db['msgs'].find({'job_id':job_id, 'call_status':'busy'}).count(),
        'Failed' : db['msgs'].find({'job_id':job_id, 'call_status':'failed'}).count()
      }
    }

    msg = utils.print_html(summary)

    fails = list( 
      db['msgs'].find(
        {'job_id':job_id, '$or': [{'email_status': 'bounced'},{'email_status': 'dropped'},{'call_status':'failed'}]},
        {'imported': 1, 'email_error': 1, 'call_error':1, 'error_code':1, 'email_status': 1, '_id': 0}
      )
    )

    if fails:
      td = '<td style="padding:5px; border:1px solid black">'
      th = '<th style="padding:5px; border:1px solid black">'

      fails_table = '<table style="padding:5px; border-collapse:collapse; border:1px solid black"><tr>'
      # Column Headers
      for field in fails[0]['imported'].keys():
        fails_table += th + field.replace('_', ' ').title() + '</th>'
      fails_table += th + 'Email Error</th>' + th + 'Call Error</th>' + th + 'Code</th>'
      fails_table += '</tr>'
      
      # Column Data 
      for row in fails:
        fails_table += '<tr>'
        for key, val in row['imported'].iteritems():
          fails_table += td + str(val) + '</td>'
        if 'email_error' in row:
          if row['email_error'].find('550') > -1:
            row['error_code'] = 550
            row['email_error'] = 'Address does not exist'
          fails_table += td + row['email_error']  + '</td>'
        else:
          fails_table += td + '</td>'
        if 'call_error' in row:
          fails_table += td + row['call_error'].replace('_', ' ').title()  + '</td>'
        else:
          fails_table += td + '</td>'
        if 'error_code' in row:
          fails_table += td + str(row['error_code']) + '</td>'
        else:
          fails_table += td + '</td>'
        fails_table += '</tr>'
      fails_table += '</table>'

      msg += '<br><br>' + fails_table

    subject = 'Job Summary %s' % job['name']
    utils.send_email(['estese@gmail.com, emptiestowinn@wsaf.ca'], subject, msg)
    logger.info('Email report sent')
  
  except Exception, e:
    logger.error('/send_email_report: %s', str(e))

#-------------------------------------------------------------------------------
@celery_app.task
def cancel_pickup(msg_id):
  try:
    msg = db['reminder_msgs'].find_one({'_id':ObjectId(msg_id)})
    # Link clicked for an outdated/in-progress or deleted job?
    if not msg:
      logger.info('No pickup request fail. Invalid msg_id')
      return 'Request unsuccessful'

    if 'no_pickup' in msg['custom']:
      logger.info('No pickup already processed for account %s', msg['imported']['account'])
      return 'Thank you'

    job = db['reminder_jobs'].find_one({'_id':msg['job_id']})

    no_pickup = 'No Pickup ' + msg['imported']['event_date'].strftime('%A, %B %d')
    db['reminder_msgs'].update(
      {'_id':msg['_id']},
      {'$set': {
        "custom.office_notes": no_pickup,
        "custom.no_pickup": True
      }}
    )
    # send_socket('update_msg', {
    #  'id': str(msg['_id']),
    #  'office_notes':no_pickup
    #  })

    # Write to eTapestry
    etap.call('no_pickup', keys, {
      "account": msg['account_id'], 
      "date": msg['custom']['next_pickup'].strftime('%d/%m/%Y'),
      "next_pickup": msg['custom']['next_pickup'].strftime('%d/%m/%Y')
    })
    
    # Send email w/ next pickup
    if 'next_pickup' in msg['custom']:
      requests.post(PUB_URL + '/email/send', {
        "recipient": msg['email']['recipient'],
        "template": "email_no_pickup.html",
        "subject": "Your next pickup"
    })

    logger.info('Emailed Next Pickup to %s', msg['email']['recipient'])

  except Exception, e:
    logger.error('/nopickup/msg_id', exc_info=True)
    return str(e)

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
def parse_csv(csvfile, template):
  reader = csv.reader(csvfile, dialect=csv.excel, delimiter=',', quotechar='"')
  buffer = []
  header_err = False 
  header_row = reader.next()

  # A. Test if file header names matche template definition
  
  if len(header_row) != len(template['import_fields']):
    header_err = True
  else:
    for col in range(0, len(header_row)):
      if header_row[col] != template['import_fields'][col]['file_header']:
        header_err = True
        break

  if header_err:
    columns = []
    for element in template['import_fields']:
      columns.append(element['file_header'])

    return 'Your file is missing the proper header rows:<br> \
    <b>' + str(columns) + '</b><br><br>' \
    'Here is your header row:<br><b>' + str(header_row) + '</b><br><br>' \
    'Please fix your mess and try again.'

  reader.next() # Delete empty Row 2 in eTapestry export file
  
  # B. Read each line from file into buffer
  
  line_num = 1
  for row in reader:
    # verify columns match template
    try:
      if len(row) != len(template['import_fields']):
        return 'Line #' + str(line_num) + ' has ' + str(len(row)) + \
        ' columns. Look at your mess:<br><br><b>' + str(row) + '</b>'
      else:
        buffer.append(row)
      line_num += 1
    except Exception as e:
      logger.info('Error reading line num ' + str(line_num) + ': ' + str(row) + '. Msg: ' + str(e))
  return buffer

#-------------------------------------------------------------------------------
def record_audio():
  if request.method == 'POST':
    to = request.form.get('to')
    logger.info('Record audio request from ' + to)
    
    r = dial(to)
    logger.info('Dial response=' + json.dumps(r))
    
    if r['call_status'] == 'queued':
      db['bravo'].insert(r)
      del r['_id']
    
    return flask.json.jsonify(r)
  elif request.method == 'GET':
    if request.args.get('Digits'):
      digits = request.args.get('Digits')
      logger.info('recordaudio digit='+digits)
      if digits == '#':
        logger.info('Recording completed. Sending audio_url to client')
        recording_info = {
          'audio_url': request.args.get('RecordingUrl'),
          'audio_duration': request.args.get('RecordingDuration'),
          'sid': request.args.get('CallSid'),
          'call_status': request.args.get('CallStatus')
        }
        db['bravo'].update({'sid': request.args.get('CallSid')}, {'$set': recording_info})
        socketio.emit('record_audio', recording_info)
        response = twilio.twiml.Response()
        response.say('Message recorded', voice='alice')
        
        return Response(str(response), mimetype='text/xml')
    else:
      logger.info('recordaudio: no digits')

    return 'OK'

#-------------------------------------------------------------------------------
def job_db_dump(job_id):
  if isinstance(job_id, str):
    job_id = ObjectId(job_id)
  job = db['reminder_jobs'].find_one({'_id':job_id})
  if 'ended_at' in job:
    time_elapsed = (job['ended_at'] - job['started_at']).total_seconds()
  else:
    time_elapsed = ''
  summary = {
    "totals": {
      "completed": {
        'answered': db['reminder_msgs'].find({'job_id':job_id, 'answered_by':'human'}).count(),
        'voicemail': db['reminder_msgs'].find({'job_id':job_id, 'answered_by':'machine'}).count()
      },
      "no-answer" : db['reminder_msgs'].find({'job_id':job_id, 'call_status':'no-answer'}).count(),
      "busy": db['reminder_msgs'].find({'job_id':job_id, 'call_status':'busy'}).count(),
      "failed" : db['reminder_msgs'].find({'job_id':job_id, 'call_status':'failed'}).count(),
      "time_elapsed": time_elapsed
    },
    "calls": list(db['reminder_msgs'].find({'job_id':job_id},{'ended_at':0, 'job_id':0}))
  }
  return summary

#-------------------------------------------------------------------------------
def allowed_file(filename):
  return '.' in filename and \
     filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS
  
#-------------------------------------------------------------------------------
def cancel_job(job_id):  
  try:
    db['reminder_jobs'].remove({'_id':ObjectId(job_id)})
    db['reminder_msgs'].remove({'job_id':ObjectId(job_id)})
    logger.info('Removed Job [ID %s]', str(job_id))

    return 'OK'
  except Exception as e:
    logger.info(str(e))
    return 'error'
      
#-------------------------------------------------------------------------------   
# POST request to create new job from new_job.html template
def submit_job(form, file):
  # A. Validate file
  try:
    if file and allowed_file(file.filename):
      filename = secure_filename(file.filename)
      file.save(os.path.join(UPLOAD_FOLDER, filename)) 
      file_path = UPLOAD_FOLDER + '/' + filename
    else:
      logger.info('could not save file')
      return {'status':'error', 'title': 'Filename Problem', 'msg':'Could not save file'}
  except Exception as e:
      logger.info(str(e))
      return {'status':'error', 'title':'file problem', 'msg':'could not upload file'}
    
  # B. Get template definition from reminder_templates.json file
  try:
    with open('templates/reminder_templates.json') as json_file:
      template_definitions = json.load(json_file)
  except Exception as e:
    Logger.error(str(e))
    return {'status':'error', 'title': 'Problem Reading reminder_templates.json File', 'msg':'Could not parse file: ' + str(e)}
      
  template = template_definitions[form['template_name']]
  
  # C. Open and parse submitted .CSV file
  try:
    with codecs.open(file_path, 'r', 'utf-8-sig') as f:
      buffer = parse_csv(f, template)
      
      if type(buffer) == str:
        return {'status':'error', 'title': 'Problem Reading File', 'msg':buffer}
   
      logger.info('Parsed %d rows from %s', len(buffer), filename) 
  except Exception as e:
    logger.error(str(e))
    return {'status':'error', 'title': 'Problem Reading File', 'msg':'Could not parse .CSV file: ' + str(e)}
  
  if not form['job_name']:
    job_name = filename.split('.')[0].replace('_',' ')
  else:
    job_name = form['job_name']
    
  try:
    fire_dtime = parse(form['date'] + ' ' + form['time'])
  except Exception as e:
    logger.error(str(e))
    return {'status':'error', 'title': 'Invalid Date', 'msg':'Could not parse the schedule date you entered: ' + str(e)}
    
  # D. Create mongo 'reminder_job' and 'reminder_msg' records

  job = {
    'name': job_name,
    'template': template,
    'fire_dtime': fire_dtime,
    'status': 'pending',
    'num_calls': len(buffer)
  }

  # Special cases
  if form['template_name'] == 'announce_voice':
    job['audio_url'] = form['audio-url']
  elif form['template_name'] == 'announce_text':
    job['message'] = form['message']
      
  job_id = db['reminder_jobs'].insert(job)
  job['_id'] = job_id

  try:
    errors = []
    reminder_msgs = []
    for idx, row in enumerate(buffer):
      msg = create_msg(job_id, template['import_fields'], idx, row, errors)
      if msg:
        reminder_msgs.append(msg)
  
    if len(errors) > 0:
      e = 'The file <b>' + filename + '</b> has some errors:<br><br>'
      for error in errors:
        e += error
      db['reminder_jobs'].remove({'_id':job_id})
      return {'status':'error', 'title':'File Format Problem', 'msg':e}
  
      db['reminder_msgs'].insert(reminder_msgs)
      logger.info('Job "%s" Created [ID %s]', job_name, str(job_id))
      
      # Special case
      if form['template_name'] == 'etw':
        scheduler.get_next_pickups.apply_async((str(job['_id']), ), queue=DB_NAME)
  
      banner_msg = 'Job \'' + job_name + '\' successfully created! ' + str(len(reminder_msgs)) + ' messages imported.'
      return {'status':'success', 'msg':banner_msg}
  except Exception as e:
    logger.info(str(e))
    return 'status':'error', 'title':'error', 'msg':str(e)}
