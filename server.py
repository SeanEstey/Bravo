from flask import Flask,render_template,request,g,Response,redirect,url_for
from flask.ext.socketio import *
from config import *
from secret import *
from bson.objectid import ObjectId
import pymongo
from celery import Celery
from celery.signals import worker_process_init
import twilio
from twilio import twiml
from datetime import datetime,date
from dateutil.parser import parse
import werkzeug
from werkzeug import secure_filename
import os
import time
import urllib2
import csv
import logging
import codecs
from reverse_proxy import ReverseProxied
import sys

def set_logger(logger, level, log_name):
  handler = logging.FileHandler(log_name)
  handler.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  handler.setFormatter(formatter)
  logger.setLevel(level)
  logger.handlers = []
  logger.addHandler(handler)

mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
db = None
logger = logging.getLogger(__name__)
set_logger(logger, LOG_LEVEL, LOG_FILE)
app = Flask(__name__)
app.config.from_pyfile('config.py')
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.debug = True
socketio = SocketIO(app)
celery_app = Celery(app.name)
celery_app.conf.update(app.config)

def is_mongodb_available():
  if mongo_client:
    if mongo_client.alive():
      return True
  else:
    return False

def reconnect_mongodb():
  global mongo_client, db
  # Either no connection handle or connection is dead
  # Attempt to re-establish 
  logger.info('Attempting to reconnect to mongodb...')
  try:
    mongo_client = pymongo.MongoClient('localhost',27017)
    db = mongo_client['wsf']
  except pymongo.errors.ConnectionFailure as e:
    logger.error('mongodb connection refused!')
    return False

  return True

def is_celery_worker():
  '''
  if not celery_app.control.inspect().active_queues():
    return False
  else:
  '''
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
      from_=FROM_NUMBER,
      to='+1'+to,
      url= os.environ['pub_url'] + '/call/answer',
      status_callback= os.environ['pub_url'] + '/call/hangup',
      status_method='POST',
      method='POST',
      if_machine='Continue'
    )
  except twilio.TwilioRestException as e:
    call_status = 'failed'
    if e.code == 21216:
      call_msg = 'not_in_service'
    elif e.code == 21211:
      call_msg = 'invalid_number'
    else:
      #logger.error('e.msg: ' + e.msg + ', e.code: ' + str(e.code))
      call_msg = str(e.code)
    return {'sid':'', 'call_status': call_status, 'call_msg':call_msg}
  except Exception as e:
    logger.error('twilio.call exception: ', exc_info=True)
  else: 
    return {'sid':call.sid, 'call_status':call.status}

def sms(to, msg):
  params = {
    'dst': '1' + to,
    'src': SMS_NUMBER,
    'text': msg,
    'type': 'sms',
    'url': os.environ['pub_url'] + '/sms_status'
  }

  try:
    plivo_api = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    response = plivo_api.send_message(params)
    return response
  except Exception as e:
    logger.error('%s SMS failed (%a)',to, str(response[0]), exc_info=True)
    return False

def get_speak(job, msg, answered_by, medium='voice'):
  if 'event_date' in msg['imported']:
    try:
      date_str = msg['imported']['event_date'].strftime('%A, %B %d')
    except TypeError:
      logger.error('Invalid date in get_speak: ' + str(msg['imported']['event_date']))
      return False

  intro_str = 'Hi, this is a friendly reminder that your empties to winn '
  repeat_voice = 'To repeat this message press 2. '
  no_pickup_voice = 'If you do not need a pickup, press 1. '
  no_pickup_sms = 'Reply with No if no pickup required.'
  speak = ''

  if job['template'] == 'etw_reminder':
    if msg['imported']['status'] == 'Dropoff':
      speak += (intro_str + 'dropoff date ' +
        'is ' + date_str + '. If you have any empties you can leave them ' +
        'out by 8am. ')
    elif msg['imported']['status'] == 'Active':
      speak += (intro_str + 'pickup date ' +
        'is ' + date_str + '. please have your empties out by 8am. ')
      if medium == 'voice' and answered_by == 'human':
        speak += no_pickup_voice
      elif medium == 'sms':
        speak += no_pickup_sms
    elif msg['imported']['status'] == 'Cancelling':
      speak += (intro_str + 'bag stand will be picked up on ' +
        date_str + '. thanks for your past support. ')
    
    if medium == 'voice' and answered_by == 'human':
      speak += repeat_voice
  elif job['template'] == 'gg_delivery':
    speak = ('Hi, this is a friendly reminder that your green goods delivery will be on ' +
      date_str + '. Your order total is ' + msg['imported']['price'] + '. ')
    if medium == 'voice' and answered_by == 'human':
      speak += repeat_voice
  elif job['template'] == 'special_msg':
    speak = job['message'] 

  return speak

def strip_phone_num(to):
  return to.replace(' ', '').replace('(','').replace(')','').replace('-','')

def create_job_summary(job_id):
  if isinstance(job_id, str):
    job_id = ObjectId(job_id)
  job = db['jobs'].find_one({'_id':job_id})
  summary = {
    "totals": {
      "completed": db['msgs'].find({'job_id':job_id, 'call_status':'completed'}).count(),
      "no-answer" : db['msgs'].find({'job_id':job_id, 'call_status':'no-answer'}).count(),
      "busy": db['msgs'].find({'job_id':job_id, 'call_status':'busy'}).count(),
      "failed" : db['msgs'].find({'job_id':job_id, 'call_status':'failed'}).count(),
      "time_elapsed": (job['ended_at'] - job['started_at']).total_seconds()
    },
    "calls": list(db['msgs'].find({'job_id':job_id},{'_id':0, 'ended_at':0, 'job_id':0, 'imported.event_date':0}))
  }
  return summary

def send_email_report(job_id):
  import smtplib
  from email.mime.text import MIMEText
  subject = 'Job Summary %s' % str(job_id)
  msg = ''
  send_email('estese@gmail.com', subject, msg)

def send_email(recipient, subject, msg):
  import requests
  send_url = 'https://api.mailgun.net/v2/' + MAILGUN_DOMAIN + '/messages'
  return requests.post(
    send_url,
    auth=('api', MAILGUN_API_KEY),
    data={
      'from': 'Empties to WINN <emptiestowinn@wsaf.ca>',
      'to': [recipient],
      'subject': subject,
      'text': msg
  })

def set_mode(mode):
  global db
  if mode == 'test':
    os.environ['title'] = 'Bravo:8080'
    os.environ['local_url'] = 'http://localhost:'+str(LOCAL_TEST_PORT)
    os.environ['pub_url'] = PUB_DOMAIN + ':' + str(PUB_TEST_PORT) + PREFIX 
    db = mongo_client[TEST_DB]
  elif mode == 'deploy':
    os.environ['title'] = 'Bravo Deploy'
    os.environ['local_url'] = 'http://localhost:'+str(LOCAL_DEPLOY_PORT)
    os.environ['pub_url'] = PUB_DOMAIN + PREFIX
    db = mongo_client[DEPLOY_DB]

@worker_process_init.connect
def init_workers(sender=None, conf=None, **kwargs):
  set_mode('test')
  print_mode()

@celery_app.task
def print_mode():
  print 'db='+str(db)+', os.environ[title]='+os.environ['title']

@celery_app.task
def execute_job(job_id):
  job_id = ObjectId(job_id)
  logger.info('execute job: os.environ[title]='+str(os.environ['title']))
  try:
    job = db['jobs'].find_one({'_id':job_id})
    # Default call order is alphabetically by name
    messages = db['msgs'].find({'job_id':job_id}).sort('name',1)
    logger.info('\n\n********** Start Job ' + str(job_id) + ' **********')
    db['jobs'].update(
      {'_id': job['_id']},
      {'$set': {
        'status': 'IN_PROGRESS',
        'started_at': datetime.now()
        }
      }
    )
    # Fire all calls
    for msg in messages:
      response = dial(msg['imported']['to'])
      logger.info('%s %s', msg['imported']['to'], response['call_status'])
      response['attempts'] = msg['attempts']+1
      db['msgs'].update(
        {'_id':msg['_id']},
        {'$set': response}
      )
      response['id'] = str(msg['_id'])
      send_socket('update_call', response)
      time.sleep(1)
    monitor_job(job_id)
    logger.info('\n********** End Job ' + str(job_id) + ' **********\n\n')
  except Exception, e:
    logger.error('execute_job job_id %s', str(job_id), exc_info=True)

def monitor_job(job_id):
  logger.info('Monitoring job %s' % str(job_id))
  try:
    while True:
      # Any calls still active?
      active = db['msgs'].find({
        'job_id': job_id,
        '$or':[
          {'call_status': 'queued'},
          {'call_status': 'ringing'},
          {'call_status': 'in-progress'}
        ]
      })
      # Any needing redial?
      incomplete = db['msgs'].find({
        'job_id':job_id,
        'attempts': {'$lt': MAX_ATTEMPTS}, 
        '$or':[
          {'call_status': 'busy'},
          {'call_status': 'no-answer'}
        ]
      })
      
      # Job Complete!
      if active.count() == 0 and incomplete.count() == 0:
        db['jobs'].update(
          {'_id': job_id},
          {'$set': {
            'status': 'COMPLETE',
            'ended_at': datetime.now()
            }
        })
        create_job_summary(job_id)
        job_complete(str(job_id))
        #completion_url = os.environ['local_url'] + '/complete/' + str(job_id)
        #requests.get(completion_url)
        #send_email_report(job_id)
        return
      # Job still in progress. Any incomplete calls need redialing?
      elif active.count() == 0 and incomplete.count() > 0:
        logger.info(str(redials.count()) + ' calls incomplete. Pausing for ' + str(REDIAL_DELAY) + 's then redialing...')
        time.sleep(REDIAL_DELAY)
        for redial in redials:
          fire_msg(redial)
      # Still active calls going out  
      else:
        time.sleep(10)
    # End loop
  except Exception, e:
    logger.error('monitor_job job_id %s', str(job_id), exc_info=True)
    return str(e)

def parse_csv(csvfile, template):
  reader = csv.reader(csvfile, dialect=csv.excel, delimiter=',', quotechar='"')
  buffer = []
  header_err = False 
  header_row = reader.next()
  logger.info('template='+str(template)) 
  logger.info('header row='+str(header_row))

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
  logger.info('Parsed ' + str(line_num) + ' rows in CSV')
  return buffer

def call_db_doc(job, idx, buf_row, errors):
  msg = {
    'job_id': job['_id'],
    'call_status': 'pending',
    'attempts': 0,
    'imported': {}
  }
  # Translate column names to mongodb names ('Phone'->'to', etc)
  logger.info(str(buf_row))
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

  #msg['to'] = bravo.strip_phone_num(msg['to'])
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
  socketio.emit('msg', 'ping from ' + mode + ' server!');

def send_socket(name, data):
# Emit socket.io msg if client connection established. Do nothing
# otherwise.
  if not socketio.server:
    return False
  logger.debug(
    'update(): num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )
  # Test for socket.io connections first
  if len(socketio.server.sockets) == 0:
    logger.info('no socket.io clients connected')
    return False
 
  socketio.emit(name, data)

@app.route('/')
def index():
  jobs = db['jobs'].find().sort('fire_dtime',-1)
  return render_template('show_jobs.html', title=os.environ['title'], jobs=jobs)

@app.route('/summarize/<job_id>')
def get_job_summary(job_id):
  job_id = job_id.encode('utf-8')
  summary = json.dumps(create_job_summary(job_id))
  return render_template('job_summary.html', title=os.environ['title'], summary=summary)

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
  if var == 'mode':
    return mode
  elif var == 'pub_url':
    return os.environ['pub_url']
  elif var == 'celery_status':
    if not is_celery_worker():
      return 'Offline'
    else:
      return 'Online'
  elif var == 'sockets':
    if not socketio.server:
      return "No sockets"
    return 'Sockets: ' + str(len(socketio.server.sockets))
  elif var == 'plivo_balance':
    #server = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    #account = server.get_account()
    #balance = account[1]['cash_credits']
    #balance = '$' + str(round(float(balance), 2))
    return ' '

  return False

@app.route('/error')
def show_error():
  msg = request.args['msg']
  return render_template('error.html', title=os.environ['title'], msg=msg)

@app.route('/new')
def new_job():
  # Create new job
  return render_template('new_job.html', title=os.environ['title'])

@app.route('/new/create', methods=['POST'])
def create_job():
  file = request.files['call_list']
  if file and allowed_file(file.filename):
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) 
    file_path = app.config['UPLOAD_FOLDER'] + '/' + filename
  else:
    msg = 'Could not save file'
    return render_template('error.html', title=os.environ['title'], msg=msg)
 
  # Open and parse file
  try:
    with codecs.open(file_path, 'r', 'utf-8-sig') as f:
      buffer = parse_csv(f, TEMPLATE[request.form['template']])
      if type(buffer) == str:
        return render_template('error.html', title=os.environ['title'], msg=buffer)
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
  job_record = {
    'name': job_name,
    'template': request.form['template'],
    'message': request.form['message'],
    'fire_dtime': fire_dtime,
    'status': 'PENDING',
    'num_calls': len(buffer)
  }
  
  job_id = db['jobs'].insert(job_record)
  job_record['_id'] = job_id
  logger.info('Job %s added to DB' % str(job_id))

  errors = []
  records = []
  for idx, row in enumerate(buffer):
    record = call_db_doc(job_record, idx, row, errors)
    if record:
      records.append(record)

  if len(errors) > 0:
    msg = 'File had the following errors:<br>' + json.dumps(errors)
    # Delete job record
    db['jobs'].remove({'_id':job_id})
    return render_template('error.html', title=os.environ['title'], msg=msg)

  db['msgs'].insert(records)
  logger.info('Calls added to DB for job %s' % str(job_id))

  return show_calls(job_id)

@app.route('/request/execute/<job_id>')
def request_execute_job(job_id):
  logger.info('executing job ' + job_id)
  execute_job.delay(job_id)
  return 'OK'

@app.route('/jobs')
def show_jobs():
  jobs = db['jobs'].find().sort('fire_dtime',-1)
  return render_template('show_jobs.html', title=os.environ['title'], jobs=jobs)

@app.route('/jobs/<job_id>')
def show_calls(job_id):
# Default sort: ascending by name
  sort_by = 'name' 
  calls = db['msgs'].find({'job_id':ObjectId(job_id)}).sort(sort_by, 1)
  job = db['jobs'].find_one({'_id':ObjectId(job_id)})

  return render_template(
    'show_calls.html', 
    title=os.environ['title'],
    calls=calls, 
    job_id=job_id, 
    job=job,
    template=TEMPLATE[job['template']]
  )

@app.route('/complete/<job_id>')
def job_complete(job_id):
  data = {
    'id': job_id,
    'status': 'COMPLETE'
  }
  
  send_socket('update_job', data)
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
      'call_msg': '',
      'message': '',
      'sid': '',
      'speak': '',
      'code': '',
      'ended_at': ''
    }},
    multi=True
  )

  db['jobs'].update(
    {'_id':ObjectId(job_id)},
    {'$set': {
      'status': 'PENDING'
    }})
  return 'OK'

@app.route('/cancel/job/<job_id>')
def cancel_job(job_id):
  db['jobs'].remove({'_id':ObjectId(job_id)})
  db['msgs'].remove({'job_id':ObjectId(job_id)})
  logger.info('Removed db.jobs and db.calls for %s' % str(job_id))

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
    logger.debug('Call answered! %s' % request.values.items())
    sid = request.form.get('CallSid')
    call_status = request.form.get('CallStatus')
    to = request.form.get('To')
    answered_by = ''
    if 'AnsweredBy' in request.form:
      answered_by = request.form.get('AnsweredBy')
    logger.info('%s %s %s /call/answer', to, call_status, answered_by)
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
    job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
    speak = get_speak(job, call, answered_by)
    db['msgs'].update({'_id':call['_id']},{'$set':{'speak':speak}})
    response = twilio.twiml.Response()
    response.say(speak)
    return Response(str(response), mimetype='text/xml')
    ''' 
    if request.method == "GET":
      getdigits_action_url = url_for('content', _external=True)
      getDigits = plivoxml.GetDigits(
        action=getdigits_action_url,
        method='POST', timeout=7, numDigits=1,
        retries=1
      )  
      response = plivoxml.Response()
      response.addWait(length=1)
      response.addSpeak(body=speak)
      response.add(getDigits)
      return Response(str(response), mimetype='text/xml')
    elif request.method == "POST":
      digit = request.form.get('Digits')
      logger.info('got digit: ' + str(digit))
      request_uuid = request.form.get('RequestUUID')
      call = db['msgs'].find_one({'request_uuid':request_uuid})
      job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
      response = plivoxml.Response()
      if digit == '1':
        speak = bravo.get_speak(job, call)
        response.addSpeak(speak)
      elif digit == '2':
        log_call_db(request_uuid, {
          'office_notes': 'NO PICKUP'
        })
        response.addSpeak('Thank you. Goodbye.')
    '''   
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
    logger.info('%s %s /call/hangup', to, call_status)
    fields = {
      'call_status': call_status,
      'ended_at': datetime.now()
    }
    call = db['msgs'].find_one({'sid':sid})

    if call_status == 'completed':
      answered_by = request.form.get('AnsweredBy')
      fields['answered_by'] = answered_by
      if 'speak' in call:
        fields['speak'] = call['speak']
    elif call_status == 'canceled':
      logger.info('canceled')
    elif call_status == 'failed':
      logger.info('failed')
    elif call_status == 'busy':
      logger.info('busy')
    elif call_status == 'no-answer':
      logger.info('no-answer')
    else:
      logger.info('unrecognized /call/hangup status: ' + call_status)

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

@app.route('/call/fallback',methods=['POST','GET'])
def process_fallback():
  try:
    '''
    post_data = str(request.form.values())
    print post_data
    logger.info('call fallback data: %s' % post_data)
    response = plivoxml.Response()
    return Response(str(response), mimetype='text/xml')
    '''
    return 'OK'
  except Exception, e:
    logger.error('%s /call/fallback' % request.values.items(), exc_info=True)
    return str(e)




if __name__ == "__main__":
  if len(sys.argv) > 0:
    mode = sys.argv[1]
    set_mode(mode)
    if mode == 'test':
      socketio.run(app, port=LOCAL_TEST_PORT)
    elif mode == 'deploy':
      socketio.run(app, port=LOCAL_DEPLOY_PORT)
