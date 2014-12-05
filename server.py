from flask import Flask,render_template,request,g,Response,redirect,url_for
#import flask.ext.socketio
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

logger = logging.getLogger(__name__)
setLogger(logger, logging.INFO, 'log.log')

app = Flask(__name__)
app.config.from_pyfile('config.py')
socketio = SocketIO(app)

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
  logger.debug('num connected sockets: ' + str(len(socketio.server.sockets)))

#-------------------------------------------------------------------
@socketio.on('connected')
def socketio_connect():
  logger.debug('socket established!')
  logger.debug('num connected sockets: ' + str(len(socketio.server.sockets)))

#-------------------------------------------------------------------
@socketio.on('update')
def send_socket_update(data):
  if not socketio.server:
    return False
  logger.debug('update(): num connected sockets: ' + str(len(socketio.server.sockets)))
  # Test for socket.io connections first
  if len(socketio.server.sockets) == 0:
    return False
  
  socketio.emit('update', data)

#-------------------------------------------------------------------
@app.route('/')
def index():
  return render_template('main.html')

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
      return redirect(url_for('show_error', msg='Could not open file'))
   
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
      'cps': CPS,
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
    
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
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

    return redirect(url_for('show_calls', job_id=job_id, calls=calls, job=job))

#-------------------------------------------------------------------
@app.route('/jobs')
def show_jobs():
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  jobs = db['jobs'].find().sort('fire_dtime',-1)

  return render_template('show_jobs.html', jobs=jobs)

#-------------------------------------------------------------------
@app.route('/jobs/<job_id>')
def show_calls(job_id):
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']

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
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  
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
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  db['jobs'].remove({'_id':ObjectId(job_id)})
  db['calls'].remove({'job_id':job_id})
  logger.info('Removed db.jobs and db.calls for %s' % job_id)

  jobs = db['jobs'].find()

  return redirect(url_for('show_jobs'))

#-------------------------------------------------------------------
@app.route('/cancel/call/<call_id>')
def cancel_call(call_id):
  job_id = request.args['job_id']
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
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
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  
  for fieldname, value in request.form.items():
    db['calls'].update(
        {'_id':ObjectId(call_id)}, 
        {'$set':{
            fieldname: value,
            }}
    )

  return 'OK'

#-------------------------------------------------------------------
@app.route('/call/ring', methods=['POST'])
def ring():
  try:
    request_uuid = request.form.get('RequestUUID')
    call_uuid = request.form.get('CallUUID')
    
    # This fields needs to be true for call to be a success,
    # unless voicemail detected (straight to voicemail)
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set':{'rang': True}}
    )
    call = db['calls'].find_one({'request_id':request_uuid})
    send_socket_update({
      'id' : str(call['_id']),
      'status' : 'dialing...',
      'message' : '',
      'attempts': call['attempts']
    })

    call_status = request.form.get('CallStatus')
    to = request.form.get('To')
    cause = request.form.get('HangupCause')
    logger.info('%s %s (%s) /call/ring', to, call_status, cause)

    return 'OK'

  except Exception, e:
    logger.error('%s rang. Failed to update DB or deliver message' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/answer',methods=['POST','GET'])
def content():
  try:
    if request.method == "GET":
      call_status = request.args.get('CallStatus')
      to = request.args.get('To')
      logger.info('%s %s /call/answer', to, call_status)
      #logger.debug('Call answered %s' % request.values.items())

      request_uuid = request.args.get('RequestUUID')
      call_uuid = request.args.get('CallUUID')
      
      client = pymongo.MongoClient('localhost',27017)
      db = client['wsf']
      db['calls'].update(
          {'request_id':request_uuid}, 
          {'$set':{
              'status': 'answered',
              'message': 'delivered', 
              'call_uuid': call_uuid
              }}
      )
      call = db['calls'].find_one({'request_id':request_uuid})
      send_socket_update({
        'id' : str(call['_id']),
        'status' : call['status'],
        'message' : call['message'],
        'attempts' : call['attempts']
      })

      dt = parse(call['event_date'])
      date_str = dt.strftime('%A, %B %d')
      job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
      speak = bravo.getSpeak(job['template'], call['etw_status'], date_str)
      logger.debug('%s Answered.' % call['to'])
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
      client = pymongo.MongoClient('localhost',27017)
      db = client['wsf']
      request_uuid = request.form.get('RequestUUID')
      call = db['calls'].find_one({'request_id':request_uuid})
      job = db['jobs'].find_one({'_id':ObjectId(call['job_id'])})
      dt = parse(call['event_date'])
      date_str = dt.strftime('%A, %B %d')
      response = plivoxml.Response()
      
      if digit == '1':
        speak = bravo.getSpeak(job['template'], call['etw_status'], date_str)
        response.addSpeak(speak)
      elif digit == '2':
        db['calls'].update(
          {'request_id':request_uuid}, 
          {'$set':{
            'office_notes': 'NO PICKUP REQUEST RECEIVED',
            }}
        )
        send_socket_update({
          'id' : str(call['_id']),
          'office_notes' : 'NO PICKUP REQUEST RECEIVED',
          'status' : call['status'],
          'message' : call['message'],
          'attempts' : call['attempts']
        })


      return Response(str(response), mimetype='text/xml')
  
  except Exception, e:
    logger.error('%s answered. Failed to update DB or deliver message' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/hangup',methods=['POST','GET'])
def process_hangup():
  try:
    call_status = request.form.get('CallStatus')
    to = request.form.get('To')
    cause = request.form.get('HangupCause')
    request_uuid = request.form.get('RequestUUID')
    
    logger.info('%s %s (%s) /call/hangup', to, call_status, cause)
    logger.debug('Call hungup %s' % request.values.items())

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']

    call = db['calls'].find_one({'request_id':request_uuid})
    attempts = int(call['attempts'])

    if call_status != 'failed':
      attempts += 1

    fields = { 
      'status': call_status,
      'code' : cause,
      'attempts': attempts
    }

    if call_status == 'failed':
      fields['message'] = cause

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
    logger.error('%s Failed to process hangup' % request.form.get('To'), exc_info=True)
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
    logger.error('%s Failed to process fallback' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/machine',methods=['POST','GET'])
def process_machine():
  try:
    to = request.form.get('To', None)
    request_uuid = request.form.get('RequestUUID')
    call_uuid = request.form.get('CallUUID')

    logger.debug('Machine detected. Transferring to voicemail. %s' % request.values.items())

    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set': {'status':'machine'}}
    )
    
    server = plivo.RestAPI(AUTH_ID, AUTH_TOKEN)
    params = {
        'call_uuid': call_uuid,
        'legs': 'aleg',
        'aleg_url' : URL+'/call/voicemail',
        'aleg_method': 'POST',
    }
    resp  = server.transfer_call(params)

    # response = plivoxml.Response()
    return Response(str(resp), mimetype='text/xml')
  
  except Exception, e:
    logger.error(
      '%s Failed to process machine detection' % 
      request.form.get('To'), exc_info=True
    )
    return str(e)

#-------------------------------------------------------------------
@app.route('/call/voicemail',methods=['POST','GET'])
def process_voicemail():
  try:
    logger.debug('Call routed to leave voicemail. %s' % request.values.items())

    request_uuid = request.form.get('RequestUUID')
    
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set': {
            'status':'voicemail',
            'message': 'left voicemail'
            }}
    )
    call = db['calls'].find_one({'request_id':request_uuid})
    dt = parse(call['event_date'])
    date_str = dt.strftime('%A, %B %d')
    speak = 'Hi, this is a friendly reminder from the winny fred stewart association that your next empties to winn pickup date is ' + date_str
   
    logger.info('%s Leaving voicemail.' % call['to'])
    
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addSpeak(body=speak)
    return Response(str(response), mimetype='text/xml')
  
  except Exception, e:
    logger.error('%s Failed to leave voicemail' % request.form.get('To'), exc_info=True)
    return str(e)

#-------------------------------------------------------------------
@app.route('/verify/<job_id>', methods = ['POST', 'GET'])
def verify(request_id):
    confirm_msg = 'Do you confirm the reminders? Use 1 to confirm and any other digit to cancel.'
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addGetDigits(
        action=app.config['URL']+'/enable/'+job_id, 
        method="POST", 
        finishOnKey='#', 
        numDigits=1, 
        playBeep=True, 
        validDigits='1').addSpeak(body=confirm_msg)

    response.addSpeak(body="No Input recieved.")
    return Response(str(response), mimetype='text/xml')

#-------------------------------------------------------------------
@app.route('/enable/<job_id>', methods=['POST'])
def enable(request_id):
    if request.method == 'POST':
        data = request.form['Digits']
        print 'data veriy: ', data

        if data[0] == '1':
            print "Customer enabled"
            tasks.fire_bulk_call.delay(job_id)
        else:
            print "customer disabled"
        return "spawned calls"

#-------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.debug = True
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['SECRET_KEY'] = 'a secret!'
    #app.run(host='0.0.0.0', port=port)
    socketio.run(app, host='0.0.0.0', port=port)
    #socketio.run(app)
