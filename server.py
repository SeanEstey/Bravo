import flask
from flask import Flask,render_template,request,g,Response,redirect,url_for
from flask.ext.socketio import *
from session import *
from config import *
from secret import *
from bson import Binary, Code, json_util
from bson.objectid import ObjectId
import pymongo
import twilio
from twilio import twiml
from datetime import datetime,date
from dateutil.parser import parse
import werkzeug
from werkzeug import secure_filename
import os
import time
import csv
import logging
import codecs
from reverse_proxy import ReverseProxied
import sys
import tasks
import utils

mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
db = mongo_client[DB_NAME]
logger = logging.getLogger(__name__)
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(LOG_LEVEL)
handler.setFormatter(formatter)
logger.setLevel(LOG_LEVEL)
logger.addHandler(handler)
app = Flask(__name__)
app.config.from_pyfile('config.py')
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.debug = True
socketio = SocketIO(app)

def celery_check():
  if not tasks.celery_app.control.inspect().active_queues():
    logger.error('Celery process not running')
    return False
  else:
    logger.info('Celery process started OK')
    return True

def restart_celery():
  logger.info('Attempting to restart celery worker...')
  try:
    os.system('./celery.sh &')
  except Exception as e:
    logger.error('Failed to restart celery worker')
    return False
  time.sleep(5)
  '''
  if not celery_app.control.inspect().active_queues():
    logger.error('Failed to restart celery worker')
    return False
  '''
  logger.info('Celery worker restarted')
  return True

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
      status_callback = PUB_URL + '/call/hangup',
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
    return {'sid':'', 'call_status': 'failed', 'error_code': e.code, 'error_msg':error_msg}
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

    return {'sid':'', 'call_status': 'failed', 'error_code': e.code, 'error_msg':error_msg}

  except Exception as e:
    logger.error('sms exception %s', str(e), exc_info=True)

    return False

def get_speak(job, msg, answered_by, medium='voice'):
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
      speak += etw_intro + 'pickup date is ' + date_str + '. Please have your empties out by 8am. '
    elif msg['imported']['status'] == 'Cancelling':
      speak += etw_intro + 'bag stand will be picked up on ' + date_str + '. Thanks for your past support. '
    elif msg['imported']['status'] == 'One-time':
      speak += etw_intro + ' one time pickup is ' + date_str + '. Please have your empties out by 8am. '
    
    if medium == 'voice' and answered_by == 'human':
      speak += repeat_voice
      if msg['imported']['status'] == 'Active':
        speak += 'If you do not need a pickup, press 2. '
    #elif medium == 'sms':
    #  speak += 'Reply with No if no pickup required.'
  elif job['template'] == 'gg_delivery':
    speak = ('Hi, this is a friendly reminder that your green goods delivery will be on ' +
      date_str + '. Your order total is ' + msg['imported']['price'] + '. ')
    if medium == 'voice' and answered_by == 'human':
      speak += repeat_voice
  elif job['template'] == 'special_msg':
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

def strip_phone_num(to):
  if not to:
    return ''

  return to.replace(' ', '').replace('(','').replace(')','').replace('-','')

def job_db_dump(job_id):
  if isinstance(job_id, str):
    job_id = ObjectId(job_id)
  job = db['jobs'].find_one({'_id':job_id})
  if 'ended_at' in job:
    time_elapsed = (job['ended_at'] - job['started_at']).total_seconds()
  else:
    time_elapsed = ''
  summary = {
    "totals": {
      "completed": {
        'answered': db['msgs'].find({'job_id':job_id, 'answered_by':'human'}).count(),
        'voicemail': db['msgs'].find({'job_id':job_id, 'answered_by':'machine'}).count()
      },
      "no-answer" : db['msgs'].find({'job_id':job_id, 'call_status':'no-answer'}).count(),
      "busy": db['msgs'].find({'job_id':job_id, 'call_status':'busy'}).count(),
      "failed" : db['msgs'].find({'job_id':job_id, 'call_status':'failed'}).count(),
      "time_elapsed": time_elapsed
    },
    "calls": list(db['msgs'].find({'job_id':job_id},{'ended_at':0, 'job_id':0}))
  }
  return summary

def send_email_report(job_id):
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

  report = {
    'Failed Calls': list( 
      db['msgs'].find(
        {'job_id':job_id, 'call_status': 'failed'}, 
        {'error_msg': 1, 'error_code': 1, 'imported': 1, '_id': 0}
      )
    ),
    'Calls Requiring Office Followup': list(
      db['msgs'].find(
        {'job_id': job_id, 'rfu': True},
        {'imported': 1, '_id': 0}
      )
    )
  }

  msg = utils.print_html(summary) + '<br><br>' + utils.print_html(report)
  subject = 'Job Summary %s' % job['name']
  utils.send_email('estese@gmail.com', subject, msg)

def parse_csv(csvfile, template):
  reader = csv.reader(csvfile, dialect=csv.excel, delimiter=',', quotechar='"')
  buffer = []
  header_err = False 
  header_row = reader.next()
  #logger.info('template='+str(template)) 
  #logger.info('header row='+str(header_row))

  if len(header_row) != len(template):
    header_err = True
  else:
    for col in range(0, len(header_row)):
      if header_row[col] != template[col]['header']:
        header_err = True
        break

  if header_err:
    return 'Your file is missing the proper header rows:<br> \
    <b>' + str(template) + '</b><br><br>' \
    'Here is your header row:<br><b>' + str(header_row) + '</b><br><br>' \
    'Please fix your mess and try again.'

  # DELETE FIRST EMPTY ROW FROM ETAP FILE EXPORT
  reader.next()
  line_num = 1
  for row in reader:
    #logger.info('row '+str(line_num)+'='+str(row)+' ('+str(len(row))+' elements)')
    # verify columns match template
    if len(row) != len(template):
      return 'Line #' + str(line_num) + ' has ' + str(len(row)) + \
      ' columns. Look at your mess:<br><br><b>' + str(row) + '</b>'
    else:
      buffer.append(row)
    line_num += 1
  return buffer

def call_db_doc(job, idx, buf_row, errors):
  msg = {
    'job_id': job['_id'],
    'call_status': 'pending',
    'attempts': 0,
    'imported': {}
  }
  # Translate column names to mongodb names ('Phone'->'to', etc)
  #logger.info(str(buf_row))
  template = TEMPLATE[job['template']]
  for col in range(0, len(template)):
    field = template[col]['field']
    if field != 'event_date':
      msg['imported'][field] = buf_row[col]
    else:
      if buf_row[col] == '':
        errors.append('Row '+str(idx+1)+ ' is missing a date<br>')
        return False
      try:
        event_dt_str = parse(buf_row[col])
        msg['imported'][field] = event_dt_str
      except TypeError as e:
        errors.append('Row '+str(idx+1)+ ' has an invalid date: '+str(buf_row[col])+'<br>')
        return False 

  msg['imported']['to'] = strip_phone_num(msg['imported']['to'])
  return msg

def allowed_file(filename):
  return '.' in filename and \
     filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@socketio.on('disconnected')
def socketio_disconnected():
  logger.debug('socket disconnected')
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )

@socketio.on('connected')
def socketio_connect():
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )
  socketio.emit('msg', 'ping from ' + DB_NAME + ' server!');

@app.route('/sendsocket', methods=['GET'])
def request_send_socket():
  name = request.args.get('name').encode('utf-8')
  data = request.args.get('data').encode('utf-8')
  send_socket(name, data)
  return 'OK'

# socket name 'update_call' must provide msg['_id'] from mongodb
# Emit socket.io msg if client connection established.
def send_socket(name, data):
  if not socketio.server:
    return False
  if len(socketio.server.sockets) == 0:
    logger.debug('No socket.io clients connected, socket not sent')
    return False
 
  socketio.emit(name, data)

@app.route('/', methods=['POST', 'GET'])
def index():
  if request.method == 'GET':
    jobs = db['jobs'].find().sort('fire_dtime',-1)
    return render_template(
      'show_jobs.html', 
      title=TITLE, 
      jobs=jobs
    )
  
  # POST request to create new job from new_job.html template
  file = request.files['call_list']
  if file and allowed_file(file.filename):
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) 
    file_path = app.config['UPLOAD_FOLDER'] + '/' + filename
  else:
    msg = 'Could not save file'
    return render_template('error.html', title=TITLE, msg=msg)
 
  # Open and parse file
  try:
    with codecs.open(file_path, 'r', 'utf-8-sig') as f:
      buffer = parse_csv(f, TEMPLATE[request.form['template']])
      if type(buffer) == str:
        return render_template('error.html', title=TITLE, msg=buffer)
      else:
        logger.info('Parsed %d rows from %s', len(buffer), filename) 
  except Exception as e:
    logger.error(str(e))
    return False

  if not request.form['job_name']:
    job_name = filename.split('.')[0].replace('_',' ')
  else:
    job_name = request.form['job_name']
  
  date_string = request.form['date']+' '+request.form['time']
  fire_dtime = parse(date_string)
  # No file errors. Save job + calls to DB.
  job = {
    'name': job_name,
    'template': request.form['template'],
    'message': request.form['message'],
    'fire_dtime': fire_dtime,
    'status': 'pending',
    'num_calls': len(buffer)
  }
  
  job_id = db['jobs'].insert(job)
  job['_id'] = job_id

  errors = []
  calls = []
  for idx, row in enumerate(buffer):
    call = call_db_doc(job, idx, row, errors)
    if call:
      calls.append(call)

  if len(errors) > 0:
    msg = 'File had the following errors:<br>' + json.dumps(errors)
    # Delete job document
    db['jobs'].remove({'_id':job_id})
    return render_template('error.html', title=TITLE, msg=msg)

  db['msgs'].insert(calls)
  logger.info('Job "%s" Created [ID %s]', job_name, str(job_id))

  jobs = db['jobs'].find().sort('fire_dtime',-1)
  banner_msg = 'Job \'' + job_name + '\' successfully created! ' + str(len(calls)) + ' calls imported.'
  return render_template(
    'show_jobs.html', 
    title=TITLE, 
    jobs=jobs, 
    banner_msg=banner_msg
  )
    
@app.route('/summarize/<job_id>')
def get_job_summary(job_id):
  job_id = job_id.encode('utf-8')
  summary = json_util.dumps(job_db_dump(job_id))
  return render_template('job_summary.html', title=TITLE, summary=summary)

@app.route('/get/template/<name>')
def get_template(name):
  if not name in TEMPLATE:
    return False
  else:
    headers = []
    for col in TEMPLATE[name]:
      headers.append(col['header'])
    return json.dumps(headers)

@app.route('/get/<var>')
def get_var(var):
  if var == 'branch_version':
    revision = os.popen('git rev-list HEAD | wc -l').read()
    return BRANCH + ' branch rev ' + revision
  elif var == 'db_name':
    return 'DB: ' + DB_NAME
  elif var == 'pub_url':
    return PUB_URL
  elif var == 'celery_status':
    if not tasks.celery_app.control.inspect().active_queues():
      return 'Celery Offline'
    else:
      return 'Celery Online'
  elif var == 'sockets':
    if not socketio.server:
      return "No sockets"
    return 'Sockets: ' + str(len(socketio.server.sockets))
  elif var == 'plivo_balance':
    return ' '

  return False

@app.route('/error')
def show_error():
  msg = request.args['msg']
  return render_template('error.html', title=TITLE, msg=msg)

@app.route('/new')
def new_job():
  return render_template('new_job.html', title=TITLE)

# POST request from client->Dial phone to record audio (routes to call/answer)
# GET request from client->Audio recording complete (hit # or hung up)
@app.route('/recordaudio', methods=['GET', 'POST'])
def record_msg():
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
        send_socket('record_audio', recording_info)
        response = twilio.twiml.Response()
        response.say('Message recorded', voice='alice')
        
        return Response(str(response), mimetype='text/xml')
    else:
      logger.info('recordaudio: no digits')

    return 'OK'

# Requested from client
@app.route('/request/execute/<job_id>')
def request_execute_job(job_id):
  job_id = job_id.encode('utf-8')
  tasks.execute_job.delay(job_id)

  return 'OK'

@app.route('/jobs/<job_id>')
def show_calls(job_id):
  sort_by = 'name' 
  calls = db['msgs'].find({'job_id':ObjectId(job_id)}).sort(sort_by, 1)
  job = db['jobs'].find_one({'_id':ObjectId(job_id)})

  return render_template(
    'show_calls.html', 
    title=TITLE,
    calls=calls, 
    job_id=job_id, 
    job=job,
    template=TEMPLATE[job['template']]
  )

# Requested on completion of tasks.execute_job()
@app.route('/fired/<job_id>')
def job_fired(job_id):
  tasks.monitor_job.delay(job_id.encode('utf-8'))
  return 'OK'
  
@app.route('/complete/<job_id>')
def job_complete(job_id):
  data = {
    'id': job_id,
    'status': 'completed'
  }
  job_id = job_id.encode('utf-8')
  
  send_socket('update_job', data)
  send_email_report(job_id)

  return 'OK'

@app.route('/reset/<job_id>')
def reset_job(job_id):
  db['msgs'].update(
    {'job_id': ObjectId(job_id)}, 
    {'$set': {
      'call_status': 'pending',
      'attempts': 0
    }},
    multi=True
  )

  db['msgs'].update(
    {'job_id': ObjectId(job_id)}, 
    {'$unset': {
      'answered_by': '',
      'error_msg': '',
      'message': '',
      'sid': '',
      'speak': '',
      'code': '',
      'ended_at': '',
      'rfu': ''
    }},
    multi=True
  )

  db['jobs'].update(
    {'_id':ObjectId(job_id)},
    {'$set': {
      'status': 'pending'
    }})

  logger.info('Reset Job [ID %s]', str(job_id))
  return 'OK'

@app.route('/cancel/job/<job_id>')
def cancel_job(job_id):
  db['jobs'].remove({'_id':ObjectId(job_id)})
  db['msgs'].remove({'job_id':ObjectId(job_id)})
  logger.info('Removed Job [ID %s]', str(job_id))

  return 'OK'

@app.route('/cancel/call', methods=['POST'])
def cancel_call():
  call_uuid = request.form.get('call_uuid')
  job_uuid = request.form.get('job_uuid')
  db['msgs'].remove({'_id':ObjectId(call_uuid)})
   
  db['jobs'].update(
    {'_id':ObjectId(job_uuid)}, 
    {'$inc':{'num_calls':-1}}
  )

  return 'OK'

@app.route('/edit/call/<call_uuid>', methods=['POST'])
def edit_call(call_uuid):
  for fieldname, value in request.form.items():
    if fieldname == 'event_date':
      try:
        value = parse(value)
      except Exception, e:
        logger.error('Could not parse event_date in /edit/call')
        return '400'
    logger.info('Editing ' + fieldname + ' to value: ' + str(value))
    field = 'imported.'+fieldname
    db['msgs'].update(
        {'_id':ObjectId(call_uuid)}, 
        {'$set':{field: value}}
    )
  return 'OK'

@app.route('/call/answer',methods=['POST','GET'])
def content():
  try:
    if request.method == 'POST':
      sid = request.form.get('CallSid')
      call_status = request.form.get('CallStatus')
      to = request.form.get('To')
      answered_by = ''
      if 'AnsweredBy' in request.form:
        answered_by = request.form.get('AnsweredBy')
      logger.info('%s %s (%s)', to, call_status, answered_by)
      call = db['msgs'].find_one({'sid':sid})

      if not call:
        # Might be special msg voice record call
        record = db['bravo'].find_one({'sid':sid})
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
        db['msgs'].update(
          {'sid':sid},
          {'$set': {'call_status':call_status}}
        )
        call = db['msgs'].find_one({'sid':sid})
        send_socket(
          'update_call', {
            'id': str(call['_id']),
            'call_status': call_status
          }
        )
        job = db['jobs'].find_one({'_id':call['job_id']})
        
        return get_speak(job, call, answered_by)
     
    elif request.method == "GET":
      sid = request.args.get('CallSid')
      call = db['msgs'].find_one({'sid':sid})
      job = db['jobs'].find_one({'_id':call['job_id']})
      digits = request.args.get('Digits')
      # Repeat Msg
      if digits == '1':
        return get_speak(job, call, 'human')
      # Special Action (defined by template)
      elif digits == '2':
        # No pickup request
        if job['template'] == 'etw_reminder':
          no_pickup = 'No Pickup ' + call['imported']['event_date'].strftime('%A, %B %d')
          db['msgs'].update(
            {'sid':sid},
            {'$set': {
              'imported.office_notes': no_pickup,
              'rfu': True
            }}
          )
          send_socket('update_call', {'office_notes':no_pickup})

    response = twilio.twiml.Response()
    response.say('Goodbye', voice='alice')
    
    return Response(str(response), mimetype='text/xml')
  except Exception, e:
    logger.error('/call/answer', exc_info=True)
    
    return str(e)

@app.route('/call/hangup',methods=['POST','GET'])
def process_status():
  try:
    logger.debug('/call/hangup values: %s' % request.values.items())
    sid = request.form.get('CallSid')
    to = request.form.get('To')
    call_status = request.form.get('CallStatus')
    logger.info('%s %s', to, call_status)
    fields = {
      'call_status': call_status,
      'ended_at': datetime.now(),
      'call_duration': request.form.get('CallDuration')
    }
    call = db['msgs'].find_one({'sid':sid})

    if not call:
      # Might be an audio recording call
      call = db['bravo'].find_one({'sid':sid})
      if call:
        logger.info('Record audio call complete')
        db['bravo'].update({'sid':sid}, {'$set': {'call_status':call_status}})
      return 'OK'

    if call_status == 'completed':
      answered_by = request.form.get('AnsweredBy')
      fields['answered_by'] = answered_by
      if 'speak' in call:
        fields['speak'] = call['speak']
    elif call_status == 'failed':
      fields['error_msg'] = 'not_in_service'

    db['msgs'].update(
      {'sid':sid},
      {'$set': fields}
    )
    fields['id'] = str(call['_id'])
    fields['attempts'] = call['attempts']
    send_socket('update_call', fields)
    return 'OK'
  except Exception, e:
    logger.error('%s /call/hangup' % request.values.items(), exc_info=True)
    return str(e)

@app.route('/sms/status', methods=['POST'])
def sms_status():
  try:
    # Using 'call_status' in DB TEMPORARILY!!!!
    items = str(request.form.items())
    logger.info(items)
    sid = request.form.get('SmsSid')
    sms_status = request.form.get('SmsStatus')
    msg_doc = db['msgs'].find_one({'sid':sid})
    if not msg_doc:
      logger.info('SmsSid not found in DB')
      return 'FAIL'

    # TODO: replace 'call_status' with 'sms_status' and refactor code
    db['msgs'].update(
      {'sid':sid},
      {'$set': {'call_status': sms_status}}
    )
    fields = {
      'id': str(msg_doc['_id']),
      'call_status': sms_status
    }
    send_socket('update_call', fields)

    return 'OK'
  except Exception, e:
    return str(e)

@app.route('/call/fallback',methods=['POST','GET'])
def process_fallback():
  try:
    '''
    post_data = str(request.form.values())
    print post_data
    logger.info('call fallback data: %s' % post_data)
    return Response(str(response), mimetype='text/xml')
    '''
    return 'OK'
  except Exception, e:
    logger.error('%s /call/fallback' % request.values.items(), exc_info=True)
    return str(e)

if __name__ == "__main__":
  os.system("ps auxww | grep 'celery' | awk '{print $2}' | xargs kill -9")
  time.sleep(2)
  os.system('celery worker -A tasks.celery_app -f celery.log -B --autoreload &')
  time.sleep(2)
  celery_check()
  logger.info('Server started OK (' + DB_NAME + ')')
  socketio.run(app, port=LOCAL_PORT)
