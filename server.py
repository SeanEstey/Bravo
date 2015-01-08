from flask import Flask,render_template,request,g,Response,redirect,url_for
from flask.ext.socketio import *
from config import *
from bson.objectid import ObjectId
import pymongo
import plivo
import plivoxml
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

#-------------------------------------------------------------------
def log_call_db(request_uuid, fields, sendSocket=True):
  call = db['msgs'].find_one({'request_uuid':request_uuid})

  if not call:
    logger.error('log_call_db(): request_uuid ' + request_uuid + ' not in db')
    return

  db['msgs'].update(
    {'request_uuid':request_uuid},
    {'$set': fields}
  )
  if sendSocket is False:
    return

  fields['id'] = str(call['_id'])
  fields['attempts'] = call['attempts']
  send_socket('update_call', fields)

#-------------------------------------------------------------------
def parse_csv(csvfile, header_template):
  reader = csv.reader(csvfile, dialect=csv.excel, delimiter=',', quotechar='"')
  buffer = []
  header_err = False 
  header_row = reader.next() 

  if len(header_row) != len(header_template):
    header_err = True
  else:
    for col in range(0, len(header_row)):
      if header_row[col] != header_template[col]:
        header_err = True
        break

  if header_err:
      msg = 'Your file is missing the proper header rows:<br> \
      <b>' + str(header_template) + '</b><br><br>' \
      'Here is your header row:<br><b>' + str(header_row) + '</b><br><br>' \
      'Please fix your mess and try again.'
      return redirect(url_for('show_error',  msg=msg))

  # DELETE FIRST EMPTY ROW FROM ETAP FILE EXPORT
  reader.next()
  line_num = 1
  for row in reader:
    # verify columns match template
    if len(row) != len(header_template):
      msg = 'Line #' + str(line_num) + ' has ' + str(len(row)) + \
      ' columns. Look at your mess:<br><br><b>' + str(row) + '</b>'
      return redirect(url_for('show_error', msg=msg))
    else:
      buffer.append(row)
    line_num += 1

  return buffer

#-------------------------------------------------------------------
def create_msg_record(job, idx, buf_row, errors):
  # Create json record to be added to mongodb
  msg = {
    'job_id': job['_id'],
    'status': 'PENDING',
    'attempts': 0
  }
  # Translate column names to mongodb names ('Phone'->'to', etc)
  headers = TEMPLATE_HEADERS[job['template']]
  for col in range(0, len(headers)):
    col_name = headers[col]
    if HEADERS_TO_MONGO[col_name] == 'event_date':
      if buf_row[col] == '':
        errors.append('Row '+str(idx+1)+ ' is missing a date<br>')
        return False
      try:
        event_dt_str = parse(buf_row[col])
        msg[HEADERS_TO_MONGO[col_name]] = event_dt_str
      except TypeError as e:
        errors.append('Row '+str(idx+1)+ ' has an invalid date: '+str(buf_row[col])+'<br>')
        return False 
    else:
      msg[HEADERS_TO_MONGO[col_name]] = buf_row[col]
  msg['to'] = bravo.strip_phone_num(msg['to'])
  return msg

#-------------------------------------------------------------------
def allowed_file(filename):
  return '.' in filename and \
     filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

#-------------------------------------------------------------------
@socketio.on('disconnected')
def socketio_disconnected():
  logger.debug('socket disconnected')
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )

#-------------------------------------------------------------------
@socketio.on('connected')
def socketio_connect():
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )
  socketio.emit('msg', 'ping from ' + mode + ' server!');

#-------------------------------------------------------------------
# Emit socket.io msg if client connection established. Do nothing
# otherwise.
def send_socket(name, data):
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

#-------------------------------------------------------------------
@app.route('/')
def index():
  jobs = db['jobs'].find().sort('fire_dtime',-1)
  return render_template('show_jobs.html', jobs=jobs)
  #return render_template('main.html')


#-------------------------------------------------------------------
@app.route('/get/template/<name>')
def get_template(name):
  if not name in TEMPLATE_HEADERS:
    return False
  else:
    return json.dumps(TEMPLATE_HEADERS[name])

#-------------------------------------------------------------------
@app.route('/get/<var>')
def get_var(var):
  if var == 'mode':
    return mode
  elif var == 'pub_url':
    if not os.environ.get('PUB_URL'):
      logger.error('No public URL!')
      return False
    if os.environ['PUB_URL'].find('localhost') >= 0: 
      return DEFAULT_PUB_URL
    return os.environ['PUB_URL']
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
    server = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    account = server.get_account()
    balance = account[1]['cash_credits']
    balance = '$' + str(round(float(balance), 2))
    return balance

  return False

#-------------------------------------------------------------------
@app.route('/error')
def show_error():
  msg = request.args['msg']
  return render_template('error.html', msg=msg)

#-------------------------------------------------------------------
@app.route('/new')
def new_job():
  return render_template('new_job.html')

#-------------------------------------------------------------------
@app.route('/new/create', methods=['POST'])
def create_job():
  # Verify and save file
  file = request.files['call_list']
  if file and allowed_file(file.filename):
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) 
    file_path = app.config['UPLOAD_FOLDER'] + '/' + filename
  else:
    return redirect(url_for('show_error', msg='Could not save file'))
 
  # Open and parse file
  try:
    with codecs.open(file_path, 'r', 'utf-8-sig') as f:
      buffer = parse_csv(f, TEMPLATE_HEADERS[request.form['template']])
      if isinstance (buffer, werkzeug.wrappers.Response):
        return buffer
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
    return redirect(url_for('show_error', msg=msg))

  db['msgs'].insert(records)
  logger.info('Calls added to DB for job %s' % str(job_id))

  return redirect(url_for(
    'show_calls', 
    job_id=str(job_id), 
    calls=db['msgs'].find({'job_id':job_id}),
    job=db['jobs'].find_one({'_id':job_id})
  ))

#-------------------------------------------------------------------
@app.route('/jobs')
def show_jobs():
  jobs = db['jobs'].find().sort('fire_dtime',-1)
  return render_template('show_jobs.html', jobs=jobs)

#-------------------------------------------------------------------
@app.route('/jobs/<job_id>')
def show_calls(job_id):
  # Default sort: ascending by name
  sort_by = 'name' 
  calls = db['msgs'].find({'job_id':ObjectId(job_id)}).sort(sort_by, 1)
  job = db['jobs'].find_one({'_id':ObjectId(job_id)})

  columns = [
    'name', 
    'to', 
    'etw_status', 
    'event_date', 
    'office_notes', 
    'status'
  ]

  return render_template(
    'show_calls.html', 
    calls=calls, 
    job_id=job_id, 
    job=job,
    columns=columns 
  )

#-------------------------------------------------------------------
@app.route('/complete/<job_id>')
def job_complete(job_id):
  data = {
    'id': job_id,
    'status': 'COMPLETE'
  }
  
  send_socket('update_job', data)
  return 'OK'

#-------------------------------------------------------------------
@app.route('/reset/<job_id>')
def reset_job(job_id):
  db['msgs'].update(
    {'job_id': ObjectId(job_id)}, 
    {'$set': {
      'status': 'PENDING',
      'attempts': 0
    }},
    multi=True
  )

  db['msgs'].update(
    {'job_id': ObjectId(job_id)}, 
    {'$unset': {
      'message_uuid': '',
      'hangup_cause': '',
      'rang': '',
      'message': '',
      'call_uuid': '',
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

#-------------------------------------------------------------------
@app.route('/cancel/job/<job_id>')
def cancel_job(job_id):
  db['jobs'].remove({'_id':ObjectId(job_id)})
  db['msgs'].remove({'job_id':ObjectId(job_id)})
  logger.info('Removed db.jobs and db.calls for %s' % str(job_id))
  jobs = db['jobs'].find()
  return redirect(url_for('show_jobs'))

#-------------------------------------------------------------------
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

#-------------------------------------------------------------------
@app.route('/edit/call/<call_uuid>', methods=['POST'])
def edit_call(call_uuid):
  for fieldname, value in request.form.items():
    if fieldname == 'event_date':
      try:
        value = parse(value)
      except Exception, e:
        logger.error('Could not parse event_date in /edit/call')
        return '400'
    db['msgs'].update(
        {'_id':ObjectId(call_uuid)}, 
        {'$set':{fieldname: value}}
    )
  return 'OK'

#-------------------------------------------------------------------
@app.route('/sms', methods=['POST'])
def get_sms():
  # Inbound SMS received
  logger.info('sms received: ' + request.values.items())
  return 'OK'

#-------------------------------------------------------------------
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

#-------------------------------------------------------------------
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

#-------------------------------------------------------------------
@app.route('/call/answer',methods=['POST','GET'])
def content():
  logger.debug('Call answered %s' % request.values.items())
  
  if request.method == "GET":
    request_uuid = request.args.get('RequestUUID')
    logger.info(
      '%s %s /call/answer', 
      request.args.get('To'), 
      request.args.get('CallStatus')
    )
    log_call_db(request_uuid, {
      'status': 'IN_PROGRESS',
      'code': 'ANSWERED',
      'call_uuid': request.args.get('CallUUID')
    })
    
    call = db['msgs'].find_one({'request_uuid':request_uuid})
    if not call:
      return Response(str(plivoxml.Response()), mimetype='text/xml')
    job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
    if not job:  
      return Response(str(plivoxml.Response()), mimetype='text/xml')
    speak = bravo.get_speak(job, call, live=True)
    if not speak:
      # ERROR
      return
    db['msgs'].update({'_id':call['_id']},{'$set':{'speak':speak}})

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
   
    return Response(str(response), mimetype='text/xml')
#  except Exception, e:
#    logger.error('%s /call/answer' % request.values.items(), exc_info=True)
#    return str(e)

#-------------------------------------------------------------------
@app.route('/call/hangup',methods=['POST','GET'])
def process_hangup():
  try:
    call_status = request.form.get('CallStatus')
    to = request.form.get('To')
    hangup_cause = request.form.get('HangupCause')
    request_uuid = request.form.get('RequestUUID')
    logger.info('%s %s (%s) /call/hangup', to, call_status, hangup_cause)
    logger.debug('Call hungup %s' % request.values.items())
    call = db['msgs'].find_one({'request_uuid':request_uuid})
    
    if not call:
      return Response(str(plivoxml.Response()), mimetype='text/xml')

    if hangup_cause == 'NORMAL_CLEARING':
      call['status'] = 'COMPLETE'
      if call['code'] == 'ANSWERED':
        call['code'] = 'SENT_LIVE'
    elif hangup_cause == 'USER_BUSY' or hangup_cause == 'NO_ANSWER':
      call['code'] = hangup_cause
      call['status'] = 'INCOMPLETE'
    elif hangup_cause == 'NORMAL_TEMPORARY_FAILURE':
      call['status'] = 'FAILED'
      call['code'] = 'NOT_IN_SERVICE'
    else:
      call['status'] = call_status
      call['code'] = hangup_cause

    call['ended_at'] = datetime.now()

    db['msgs'].update(
        {'request_uuid':request_uuid}, 
        {'$set': {
          'code': call['code'],
          'status': call['status'],
          'hangup_cause': hangup_cause,
          'ended_at': call['ended_at']
          }
        }
    )

    payload = {
      'id' : str(call['_id']),
      'status' : call['status'],
      'code': call['code'],
      'attempts': call['attempts'],
      'ended_at': call['ended_at']
    }
    
    if call['status'] == 'COMPLETE' and 'speak' in call:
      payload['speak'] = call['speak']

    send_socket('update_call', payload)

    response = plivoxml.Response()
    return Response(str(response), mimetype='text/xml')

  except Exception, e:
    logger.error('%s /call/hangup' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/fallback',methods=['POST','GET'])
def process_fallback():
  try:
    post_data = str(request.form.values())
    print post_data
    logger.info('call fallback data: %s' % post_data)
    response = plivoxml.Response()
    return Response(str(response), mimetype='text/xml')
  except Exception, e:
    logger.error('%s /call/fallback' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/machine',methods=['POST','GET'])
def process_machine():
  try:
    logger.debug('Machine detected. %s' % request.values.items())
    log_call_db(request.form.get('RequestUUID'), {
      'code': 'MACHINE_ANSWERED'
    })
    call_uuid = request.form.get('CallUUID')
    server = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    response = server.transfer_call({
      'call_uuid': call_uuid,
      'legs': 'aleg',
      'aleg_url' : bravo.pub_url +'/call/voicemail',
      'aleg_method': 'POST'
    })
    logger.info('/call/machine forwarding to url: ' + bravo.pub_url + '/call/voicemail')
    return Response(str(response), mimetype='text/xml')
  except Exception, e:
    logger.error('%s /call/machine' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/voicemail',methods=['POST','GET'])
def process_voicemail():
  try:
    logger.debug('/call/voicemail: %s' % request.values.items())
    request_uuid = request.form.get('RequestUUID')
    log_call_db(request_uuid, {
      'code': 'SENT_VOICEMAIL'
    })
    call = db['msgs'].find_one({'request_uuid':request_uuid})
    job = db['jobs'].find_one({'_id':call['job_id']})
    speak = bravo.get_speak(job, call)
    db['msgs'].update({'_id':call['_id']},{'$set':{'speak':speak}})
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addSpeak(body=speak)
    logger.info('%s Leaving voicemail.' % call['to'])
    return Response(str(response), mimetype='text/xml')
  except Exception, e:
    logger.error('%s /call/voicemail' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
if __name__ == "__main__":
  client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
  if len(sys.argv) > 0:
    mode = sys.argv[1]
    bravo.set_mode(mode)
    if mode == 'test':
      db = client[TEST_DB]
      socketio.run(app, port=TEST_PORT)
    elif mode == 'deploy':
      db = client[DEPLOY_DB]
      socketio.run(app, port=DEPLOY_PORT)
    

