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
import tasks
import urllib2
import csv
import logging
import codecs
import bravo
from bravo import log_call_db

logger = logging.getLogger(__name__)
setLogger(logger, logging.INFO, 'log.log')
app = Flask(__name__)
app.config.from_pyfile('config.py')
socketio = SocketIO(app)
client = pymongo.MongoClient('localhost',27017)
db = client['wsf']

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
  logger.info('socket established!')
  logger.debug(
    'num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )

#-------------------------------------------------------------------
@socketio.on('update')
def send_socket_update(data):
  if not socketio.server:
    return False
  logger.debug(
    'update(): num connected sockets: ' + 
    str(len(socketio.server.sockets))
  )
  # Test for socket.io connections first
  if len(socketio.server.sockets) == 0:
    return False
 
  socketio.emit('update', data)

#-------------------------------------------------------------------
@app.route('/')
def index():
  return render_template('main.html')

#-------------------------------------------------------------------
@app.route('/account')
def get_account():
  server = plivo.RestAPI(AUTH_ID, AUTH_TOKEN)
  account = server.get_account()
  balance = account[1]['cash_credits']
  balance = '$' + str(round(float(balance), 2))
  return balance

#-------------------------------------------------------------------
@app.route('/celery_status')
def celery_status():
  if not bravo.is_active_worker():
    return 'Offline'
  else:
    return 'Online'
  
#-------------------------------------------------------------------
@app.route('/status')
def status():
  if not socketio.server:
    return "No sockets"
  return 'Sockets: ' + str(len(socketio.server.sockets))

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
  if request.method == 'POST':
    date_string = request.form['date']+' '+request.form['time']
    fire_dtime = parse(date_string)
    file = request.files['call_list']
    filename = ''
    if file and allowed_file(file.filename):
      filename = secure_filename(file.filename)
      file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) 
    else:
      return redirect(url_for(
        'show_error', 
        msg='Could not open file')
      )
   
    file_path = app.config['UPLOAD_FOLDER'] + '/' + filename
    with codecs.open(file_path, 'r', 'utf-8-sig') as f:
      buffer = parse_csv(f, TEMPLATE_HEADERS[request.form['template']])
      if isinstance (buffer, werkzeug.wrappers.Response):
        return buffer

    if not request.form['job_name']:
      job_name = filename.split('.')[0].replace('_',' ')
    else:
      job_name = request.form['job_name']
    
    # No file errors. Save job + calls to DB.
    job_record = {
      'name': job_name,
      'auth_id': AUTH_ID,
      'auth_token': AUTH_TOKEN,
      'max_attempts': MAX_ATTEMPTS,
      'template': request.form['template'],
      'verify_phone': request.form['verify_phone'],
      'message': request.form['message'],
      'audio_url': request.form['audio'],
      'audio_order': request.form['order'],
      'fire_dtime': fire_dtime,
      'status': 'pending',
      'num_calls': len(buffer)
    }
    
    job_id = db['jobs'].insert(job_record)
    job_id = str(job_id)
    logger.info('Job %s added to DB' % job_id)

    list_of_calls = []
    for row in buffer:
      call = {
        'job_id': job_id,
        'status': 'not attempted',
        'attempts': 0
      }
      # Add data columns to list with proper mongodb names ('Phone'->'to', etc)
      for col in range(0, len(TEMPLATE_HEADERS[request.form['template']])):
        col_name = TEMPLATE_HEADERS[request.form['template']][col]
        call[HEADERS_TO_MONGO[col_name]] = row[col]

      call['to'] = call['to'].replace(' ', '').replace('(','').replace(')','').replace('-','')

      list_of_calls.append(call)

    db['calls'].insert(list_of_calls)
    logger.info('Calls added to DB for job %s' % job_id)

    calls = db['calls'].find({'job_id':job_id})
    job = db['jobs'].find_one({'_id':ObjectId(job_id)})

    return redirect(url_for(
      'show_calls', 
      job_id=job_id, 
      calls=calls, 
      job=job)
    )

#-------------------------------------------------------------------
@app.route('/jobs')
def show_jobs():
  jobs = db['jobs'].find().sort('fire_dtime',-1)
  return render_template('show_jobs.html', jobs=jobs)

#-------------------------------------------------------------------
@app.route('/jobs/<job_id>')
def show_calls(job_id):
  if 'sort_by' not in request.args:
    sort_by = 'name'
    sort_order = 1
  else:
    sort_by = request.args['sort_by']
    sort_order = int(request.args['sort_order'])
  
  calls = db['calls'].find({'job_id':job_id}).sort(sort_by, sort_order)
  job = db['jobs'].find_one({'_id':ObjectId(job_id)})

  sort_cols = [
    {'name': 1},
    {'to': 1},
    {'etw_status': 1},
    {'event_date': 1},
    {'office_notes': 1},
    {'status': 1},
    {'message': 1},
    {'attempts': 1}
  ]

  index = 0
  for col in sort_cols:
    if col.keys()[0] == sort_by:
      break;
    index += 1

  if sort_order == -1:
    sort_cols[index][sort_by] = 1
  else:
    sort_cols[index][sort_by] = -1

  return render_template(
    'show_calls.html', 
    calls=calls, 
    job_id=job_id, 
    job=job, 
    sort_by=sort_by,
    sort_order=sort_order,
    sort_cols=sort_cols
  )

#-------------------------------------------------------------------
@app.route('/reset/<job_id>')
def reset_job(job_id):
  db['calls'].update(
    {'job_id': job_id}, 
    {'$set': {
      'status': 'not attempted',
      'attempts': 0
    }},
    multi=True
  )

  db['calls'].update(
    {'job_id': job_id}, 
    {'$unset': {
      'message': '',
      'call_uuid': '',
      'request_id': '',
      'code': ''
    }},
    multi=True
  )

  db['jobs'].update(
    {'_id':ObjectId(job_id)},
    {'$set': {
      'status': 'pending'
    }})

  return 'OK'

#-------------------------------------------------------------------
@app.route('/cancel/job/<job_id>')
def cancel_job(job_id):
  db['jobs'].remove({'_id':ObjectId(job_id)})
  db['calls'].remove({'job_id':job_id})
  logger.info('Removed db.jobs and db.calls for %s' % job_id)

  jobs = db['jobs'].find()

  return redirect(url_for('show_jobs'))

#-------------------------------------------------------------------
@app.route('/cancel/call/<call_id>')
def cancel_call(call_id):
  job_id = request.args['job_id']
  db['calls'].remove({'_id':ObjectId(call_id)})
   
  db['jobs'].update(
    {'_id':ObjectId(job_id)}, 
    {'$inc':{'num_calls':-1}}
  )

  return redirect(url_for(
    'show_calls', 
    job_id=job_id, 
    sort_by=request.args['sort_by'], 
    sort_order=request.args['sort_order']
  ))

#-------------------------------------------------------------------
@app.route('/edit/call/<call_id>', methods=['POST'])
def edit_call(call_id):
  for fieldname, value in request.form.items():
    db['calls'].update(
        {'_id':ObjectId(call_id)}, 
        {'$set':{fieldname: value}}
    )
  return 'OK'

#-------------------------------------------------------------------
@app.route('/sms', methods=['POST'])
def sms():
  for fieldname, value in request.form.items():
    logger.info('field: ' + fieldname + ', val: ' + str(value))

  message_uuid = request.form.get('MessageUUID')
  status = request.form.get('Status')

  db['calls'].update(
      {'message_id':message_uuid}, 
      {'$set':{
        'status': status,
        'code': status
  }})
  call = db['calls'].find_one({'message_id':message_uuid})
  send_socket_update({
    'id' : str(call['_id']),
    'status' : status,
    'message' : status,
    'attempts': call['attempts']
  })
  return 'OK'

#-------------------------------------------------------------------
@app.route('/call/ring', methods=['POST'])
def ring():
  try:
    log_call_db(request.form.get('RequestUUID'), {
      'status': 'in progress',
      'message': 'RINGING',
      'code': 'RINGING',
      'rang': True
    })
    logger.info(
      '%s %s /call/ring', 
      request.form.get('To'), 
      request.form.get('CallStatus')
    )
    return 'OK'
  except Exception, e:
    logger.error('%s /call/ring.' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/answer',methods=['POST','GET'])
def content():
  try:
    logger.debug('Call answered %s' % request.values.items())
    
    if request.method == "GET":
      request_uuid = request.args.get('RequestUUID')
      logger.info(
        '%s %s /call/answer', 
        request.args.get('To'), 
        request.args.get('CallStatus')
      )
      log_call_db(request_uuid, {
        'status': 'in progress',
        'message': 'ANSWERED',
        'code': 'ANSWERED',
        'call_uuid': request.args.get('CallUUID')
      })
      
      call = db['calls'].find_one({'request_id':request_uuid})
      job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
      speak = bravo.getSpeak(
        job['template'], 
        call['etw_status'], 
        call['event_date']
      )
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
      call = db['calls'].find_one({'request_id':request_uuid})
      job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
      response = plivoxml.Response()
      
      if digit == '1':
        speak = bravo.getSpeak(
          job['template'], 
          call['etw_status'], 
          call['event_date']
        )
        response.addSpeak(speak)
      elif digit == '2':
        log_call_db(request_uuid, {
          'office_notes': 'NO PICKUP'
        })
        response.addSpeak('Thank you. Goodbye.')
      return Response(str(response), mimetype='text/xml')
  except Exception, e:
    logger.error('%s /call/answer' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/hangup',methods=['POST','GET'])
def process_hangup():
  try:
    call_status = request.form.get('CallStatus')
    to = request.form.get('To')
    code = request.form.get('HangupCause')
    request_uuid = request.form.get('RequestUUID')
    
    logger.info('%s %s (%s) /call/hangup', to, call_status, code)
    logger.debug('Call hungup %s' % request.values.items())

    call = db['calls'].find_one({'request_id':request_uuid})
    if 'attempts' in call:
      attempts = int(call['attempts'])
    else:
      attempts = 0

    if call_status != 'failed':
      attempts += 1

    fields = { 
      'status': call_status,
      #'code': code,
      'attempts': attempts,
      'hangup_cause': code
    }

    if code == 'NORMAL_CLEARING':
      fields['message'] = call['message']
      if call['code'] == 'ANSWERED':
        fields['code'] = 'DELIVERED'
      elif call['code'] == 'DELIVERED_VOICEMAIL':
        fields['code'] = 'DELIVERED_VOICEMAIL'
    else:
      fields['code'] = code

    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set': fields}
    )
    send_socket_update({
      'id' : str(call['_id']),
      'status' : fields['status'],
      'message' : fields['code'],
      'attempts': fields['attempts']
    })

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
      'status': 'machine',
      'message': 'LEAVING_VOICEMAIL',
      'code': 'LEAVING_VOICEMAIL'
    })
    call_uuid = request.form.get('CallUUID')
    server = plivo.RestAPI(AUTH_ID, AUTH_TOKEN)
    response = server.transfer_call({
      'call_uuid': call_uuid,
      'legs': 'aleg',
      'aleg_url' : URL+'/call/voicemail',
      'aleg_method': 'POST'
    })
    return Response(str(response), mimetype='text/xml')
  except Exception, e:
    logger.error('%s /call/machine' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/voicemail',methods=['POST','GET'])
def process_voicemail():
  try:
    logger.debug('/call/voicemail: %s' % request.values.items())
    request_id = request.form.get('RequestUUID')
    log_call_db(request_id, {
      'status': 'completed',
      'message': 'DELIVERED_VOICEMAIL',
      'code': 'DELIVERED_VOICEMAIL'
    })
    call = db['calls'].find_one({'request_id':request_id})
    job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
    speak = bravo.getSpeak(
      job['template'], 
      call['etw_status'], 
      call['event_date']
    )
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
    port = int(os.environ.get('PORT', 5000))
    app.debug = True
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['SECRET_KEY'] = 'a secret!'
    socketio.run(app, host='0.0.0.0', port=port)
