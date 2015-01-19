from flask import Flask,render_template,request,g,Response,redirect,url_for
from flask.ext.socketio import *
from config import *
from secret import *
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
import urllib2
import csv
import logging
import codecs
import bravo
from reverse_proxy import ReverseProxied
import sys


logger = logging.getLogger(__name__)
bravo.set_logger(logger, LOG_LEVEL, LOG_FILE)
app = Flask(__name__)
app.config.from_pyfile('config.py')
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.debug = True
socketio = SocketIO(app)

def log_call_db(sid, fields, sendSocket=True):
  call = db['msgs'].find_one({'sid':sid})

  if not call:
    logger.error('log_call_db(): sid ' + sid + ' not in db')
    return

  db['msgs'].update(
    {'sid':sid},
    {'$set': fields}
  )
  if sendSocket is False:
    return

  fields['id'] = str(call['_id'])
  fields['attempts'] = call['attempts']
  send_socket('update_call', fields)

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

def create_msg_record(job, idx, buf_row, errors):
  # Create json record to be added to mongodb
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

@app.route('/send_socket', method=['POST'])
def post_socket():
  

@app.route('/summarize/<job_id>')
def get_job_summary(job_id):
  job_id = job_id.encode('utf-8')
  summary = bravo.create_job_summary(job_id)
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
    return bravo.pub_url
  elif var == 'celery_status':
    if not bravo.is_celery_worker():
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
    record = create_msg_record(job_record, idx, row, errors)
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

@app.route('/execute/<job_id>')
def execute_job(job_id):
  job_id = job_id.encode('utf-8')
  logger.info(type(job_id))
  logger.info('job_id: ' + job_id)
  bravo.execute_job(job_id);

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
      'message_uuid': '',
      'answered_by': '',
      'call_msg': '',
      'hangup_cause': '',
      'rang': '',
      'message': '',
      'sid': '',
      'call_uuid': '',
      'status': '',
      'request_uuid': '',
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

@app.route('/sms', methods=['POST'])
def get_sms():
  logger.info('sms received: ' + request.values.items())
  return 'OK'

@app.route('/sms_status', methods=['POST'])
def get_sms_status():
  try:
    message_uuid = request.form.get('MessageUUID')
    status = request.form.get('Status')
    logger.info('%s (%s) /sms id: %s ', request.form.get('To'), status, message_uuid)

    fields = {
      'status': status,
      'code': status
    }

    if status == 'sent':
      fields['status'] = 'COMPLETE'
      fields['code'] = 'SENT_SMS'
      fields['ended_at'] = datetime.now()

    db['msgs'].update(
        {'message_uuid':message_uuid}, 
        {'$set': fields}
    )
    res = call = db['msgs'].find_one({'message_uuid':message_uuid})
    if res is None:
      return 'NO'

    send_socket('update_call',{
      'id' : str(call['_id']),
      'status' : fields['status'],
      'code' : fields['code'],
      'attempts': call['attempts'],
      'speak': call['speak'],
      'ended_at': fields['ended_at']
    })
    return 'OK'
  except Exception, e:
    logger.error('%s /sms.' % request.values.items(), exc_info=True)
    return str(e)

@app.route('/call/ring', methods=['POST'])
def ring():
  try:
    log_call_db(request.form['RequestUUID'], {
      'status': 'IN_PROGRESS',
      'code': 'RINGING',
      'rang': True
    })
    logger.info(
      '%s %s /call/ring', 
      request.form['To'], 
      request.form['CallStatus']
    )
    return 'OK'
  except Exception as e:
    logger.error(str(e))
    return 'FAIL'

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
    log_call_db(sid, {
      'call_status': call_status,
      'call_msg': 'answered'
    })
    call = db['msgs'].find_one({'sid':sid})
    job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
    speak = bravo.get_speak(job, call, answered_by)
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

@app.route('/call/status',methods=['POST','GET'])
def process_status():
  try:
    logger.debug('/call/status values: %s' % request.values.items())
    sid = request.form.get('CallSid')
    to = request.form.get('To')
    call_status = request.form.get('CallStatus')
    logger.info('%s %s /call/status', to, call_status)
    fields = {}
    fields['call_status'] = call_status
    call = db['msgs'].find_one({'sid':sid})

    if call_status == 'completed':
      answered_by = request.form.get('AnsweredBy')
      fields['answered_by'] = answered_by
      fields['call_status'] = call_status
      fields['ended_at'] = datetime.now()
      if 'speak' in call:
        fields['speak'] = call['speak']
    elif call_status == 'ringing':
      logger.debug('ringing')
    elif call_status == 'in-progress':
      logger.debug('in-progress')
    elif call_status == 'canceled':
      logger.debug('canceled')
    elif call_status == 'failed':
      logger.debug('failed')
    elif call_status == 'busy':
      logger.debug('busy')
    elif call_status == 'no-answer':
      logger.debug('no-answer')
    else:
      logger.debug('wtf')

    log_call_db(sid, fields)
   
    fields['id'] = str(call['_id'])
    fields['attempts'] = call['attempts']
    send_socket('update_call', fields)

    return 'OK'
  except Exception, e:
    logger.error('%s /call/status' % request.values.items(), exc_info=True)
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
  client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
  if len(sys.argv) > 0:
    mode = sys.argv[1]
    bravo.set_mode(mode)
    if mode == 'test':
      os.environ['title'] = 'Bravo:8080'
      db = client[TEST_DB]
      socketio.run(app, port=LOCAL_TEST_PORT)
    elif mode == 'deploy':
      os.environ['title'] = 'Bravo Deploy'
      db = client[DEPLOY_DB]
      socketio.run(app, port=LOCAL_DEPLOY_PORT)
    

