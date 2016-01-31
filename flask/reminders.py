import twilio
from twilio import twiml
from bson import Binary, Code, json_util
from bson.objectid import ObjectId
import flask
from flask import Flask,render_template,request,g,Response,redirect,url_for
from datetime import datetime,date
from dateutil.parser import parse
import werkzeug
from werkzeug import secure_filename


from app import app, celery_app, db, logger, login_manager
import utils
from config import *
from server_settings import *

def view_main():
  if request.method == 'GET':
    # If no 'n' specified, display records (sorted by date) {1 .. JOBS_PER_PAGE}
    # If 'n' arg, display records {n .. n+JOBS_PER_PAGE}
    start_record = request.args.get('n')
    if start_record:
      jobs = db['reminder_jobs'].find().sort('fire_dtime',-1)
      jobs.skip(int(start_record)).limit(JOBS_PER_PAGE);
    else:
      jobs = db['reminder_jobs'].find().sort('fire_dtime',-1).limit(JOBS_PER_PAGE)

    return render_template(
      'show_jobs.html', 
      title=None,
      #title=TITLE, 
      jobs=jobs
    )

@celery_app.task
def run_scheduler():
  pending_jobs = db['jobs'].find({'status': 'pending'})
  
  print(str(pending_jobs.count()) + ' pending jobs:')

  job_num = 1
  for job in pending_jobs:
    if datetime.now() > job['fire_dtime']:
      logger.info('Scheduler: Starting Job...')
      execute_job.apply_async((str(job['_id']), ), queue=DB_NAME)
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

@celery_app.task
def execute_job(job_id):
  try:
    job_id = ObjectId(job_id)
    job = db['jobs'].find_one({'_id':job_id})
    # Default call order is alphabetically by name
    messages = db['msgs'].find({'job_id':job_id}).sort('name',1)
    logger.info('\n\nStarting Job %s [ID %s]', job['name'], str(job_id))
    db['jobs'].update(
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
    r = requests.get(LOCAL_URL+'/fired/' + str(job_id))
    return 'OK'

  except Exception, e:
    logger.error('execute_job job_id %s', str(job_id), exc_info=True)

@celery_app.task
def monitor_job(job_id):
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
    logger.error('monitor_job job_id %s', str(job_id), exc_info=True)

def dial(to):
  try:
    twilio_client = twilio.rest.TwilioRestClient(
      TWILIO_ACCOUNT_SID, 
      TWILIO_AUTH_ID
    )
    call = twilio_client.calls.create(
      from_ = FROM_NUMBER,
      to = '+1'+to,
      url = PUB_URL + '/call/answer',
      status_callback = PUB_URL + '/call/status',
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

def strip_phone(to):
  if not to:
    return ''

  return to.replace(' ', '').replace('(','').replace(')','').replace('-','')


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

  repeat_voice = 'To repeat this message press 1. '
  speak = ''

  if job['template'] == 'etw_reminder':
    etw_intro = 'Hi, this is a friendly reminder that your Empties to WINN '
    if msg['imported']['status'] == 'Dropoff':
      speak += etw_intro + 'dropoff date is ' + date_str + '. If you have any empties you can leave them out by 8am. '
    elif msg['imported']['status'] == 'Active':
      speak += etw_intro + 'pickup date is ' + date_str + '. Please have your green bags out by 8am. Glass can be separated into cases. Your pickup date again is ' + date_str + '. '
    elif msg['imported']['status'] == 'Cancelling':
      speak += etw_intro + 'bag stand will be picked up on ' + date_str + '. Thanks for your past support. '
    elif msg['imported']['status'] == 'One-time':
      speak += etw_intro + ' one time pickup is ' + date_str + '. Please have your empties out by 8am. '
    
    if medium == 'voice' and answered_by == 'human':
      speak += repeat_voice
      if msg['imported']['status'] == 'Active':
        speak += 'If you do not need a pickup, press 2. '

  elif job['template'] == 'gg_delivery':
    speak = ('Hi, this is a friendly reminder that your green goods delivery will be on ' +
      date_str + '. Your order total is ' + msg['imported']['price'] + '. ')
    if medium == 'voice' and answered_by == 'human':
      speak += repeat_voice
  elif job['template'] == 'announce_text':
    speak = job['message']
    if medium == 'voice' and answered_by == 'human':
      speak += repeat_voice
    
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


def get_no_pickup_html_body(next_pickup_dt):
  date_str = next_pickup_dt.strftime('%A, %B %d')

  body = '''
    <html>
      <body style='font-size:12pt; text-align:left'>
        <div>
          <p>Thanks for letting us know you don't need a pickup. 
          This helps us to be more efficient with our resources.</p>
          
          <p>Your next pickup date will be on:</p>
          <p><h3>!DATE!</h3></p>
        </div>
        <div>
          1-888-YOU-WINN
          <br>
          <a href='http://www.emptiestowinn.com'>www.emptiestowinn.com</a>
        </div>
      </body>
    </html>
  '''

  body = body.replace('!DATE!', date_str)

  return body

def get_reminder_html_body(job, msg):
  try:
    date_str = msg['imported']['event_date'].strftime('%A, %B %d')
  except TypeError:
    logger.error('Invalid date in get_email: ' + str(msg['imported']['event_date']))
    return False

  if job['template'] == 'etw_reminder':
    if msg['imported']['status'] == 'Active' or msg['imported']['status'] == 'Call-in' or msg['imported']['status'] == 'One-time':
      a_style = '''
        color:#ffffff!important;
        display:inline-block;
        font-weight:500;
        font-size:16px;
        line-height:42px;
        font-family:\'Helvetica\',Arial,sans-serif;
        width:auto;
        white-space:nowrap;
        min-height:42px;
        margin-top:12px;
        margin-bottom:12px;
        padding-top:0px;
        padding-bottom:0px;
        padding-left:22px;
        padding-right:22px;
        text-decoration:none;
        text-align:center;
        border:0;
        border-radius:3px;
        vertical-align:top;
        background-color:#337ab7!important
      '''.replace('\n', '').replace(' ', '')

      body = '''
        <html>
          <body style='font-size:12pt; text-align:left'>
            <div>
              <p>Hi, your upcoming Empties to WINN pickup date is</p>
              <p><h3>!DATE!</h3></p>
              <p>Your green bags can be placed at your front entrance, visible from the street, by 8am. 
              Please keep each bag under 30lbs.  
              Extra glass can be left in cases to the side.</p>
              <p><a style="!STYLE!" href='!HREF!'>Click here to cancel your pickup</a></p>
            </div>
            <div>
              1-888-YOU-WINN
              <br>
              <a href='http://www.emptiestowinn.com'>www.emptiestowinn.com</a>
            </div>
          </body>
        </html>
      '''

      body = body.replace('!DATE!', date_str)
      body = body.replace('!STYLE!', a_style)
      body = body.replace('!HREF!', PUB_URL + '/nopickup/' + str(msg['_id']))
    elif msg['imported']['status'] == 'Dropoff':
      return False
    elif msg['imported']['status'] == 'Cancelling':
      body = '''
        <html>
          <body style='font-size:12pt; text-align:left;'>
            <p>Hi, this is a reminder that a driver will be by on !DATE! 
            to pickup your Empties to WINN collection stand.
            Thanks for your support.</p>
            <div>
              1-888-YOU-WINN
              <br>
              <a href='http://www.emptiestowinn.com'>www.emptiestowinn.com</a>
            </div>
          </body>
        </html>
      '''

      body = body.replace('!DATE!', date_str)

    return body


def parse_csv(csvfile, template):
  reader = csv.reader(csvfile, dialect=csv.excel, delimiter=',', quotechar='"')
  buffer = []
  header_err = False 
  header_row = reader.next()

  if len(header_row) != len(template):
    header_err = True
  else:
    for col in range(0, len(header_row)):
      if header_row[col] != template[col]['header']:
        header_err = True
        break

  if header_err:
    columns = []
    for element in template:
      columns.append(element['header'])

    return 'Your file is missing the proper header rows:<br> \
    <b>' + str(columns) + '</b><br><br>' \
    'Here is your header row:<br><b>' + str(header_row) + '</b><br><br>' \
    'Please fix your mess and try again.'

  # DELETE FIRST EMPTY ROW FROM ETAP FILE EXPORT
  reader.next()
  line_num = 1
  for row in reader:
    #logger.info('row '+str(line_num)+'='+str(row)+' ('+str(len(row))+' elements)')
    # verify columns match template
    try:
      if len(row) != len(template):
        return 'Line #' + str(line_num) + ' has ' + str(len(row)) + \
        ' columns. Look at your mess:<br><br><b>' + str(row) + '</b>'
      else:
        buffer.append(row)
      line_num += 1
    except Exception as e:
      logger.info('Error reading line num ' + str(line_num) + ': ' + str(row) + '. Msg: ' + str(e))
  return buffer

def record_audio():
  if request.method == 'POST':
    to = request.form.get('to')
    logger.info('Record audio request from ' + to)
    
    r = reminders.dial(to)
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
        send_socket('record_audio', recording_info)
        response = twilio.twiml.Response()
        response.say('Message recorded', voice='alice')
        
        return Response(str(response), mimetype='text/xml')
    else:
      logger.info('recordaudio: no digits')

    return 'OK'
