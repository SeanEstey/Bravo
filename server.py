from flask import Flask,render_template,request,g,Response,redirect,url_for
from config import *
from bson.objectid import ObjectId
import pymongo
import plivo
import plivoxml
from datetime import datetime,date
from dateutil.parser import parse
from werkzeug import secure_filename
import os
import time
import tasks
import urllib2
import csv
import logging

logger = logging.getLogger(__name__)
setLogger(logger, logging.INFO, 'log.log')

app = Flask(__name__)
app.config.from_pyfile('config.py')

#-------------------------------------------------------------------
def allowed_file(filename):
  return '.' in filename and \
     filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

#-------------------------------------------------------------------
@app.route('/')
def index():
  return render_template('main.html')

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

    if request.form['order'] == 'after':
      order = False
    else:
      order = True

    file = request.files['call_list']
    filename = ''
    if file and allowed_file(file.filename):
      filename = secure_filename(file.filename)
      file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) 
    else:
      return redirect(url_for('show_error', msg='Could not open file'))
    
    with open(app.config['UPLOAD_FOLDER'] + '/' + filename, 'rb') as csvfile:
      reader = csv.reader(csvfile, delimiter=',', quotechar='"')
      list_of_calls = []
      buffer = []
      template = request.form['template']
      if template == 'etw_reminder':
        header = reader.next()
        if header[0] != 'Name' or \
           header[1] != 'Phone' or \
           header[2] != 'Status' or \
           header[3] != 'Date' or \
           header[4] != 'Office Notes':
           msg = 'Your file is missing the proper header rows:<br> \
           <b>[Name, Phone, Status, Date, Office Notes]</b><br><br>' \
           'Here is your header row:<br><b>' + str(header) + '</b><br><br>' \
           'Please fix your mess and try again.'
           return redirect(url_for('show_error',  msg=msg))
      
      for row in reader:
        # CSV format: NAME,PICKUP_DATE,PHONE
        # verify columns match template
        if len(row) != 5:
          msg = 'Line #' + str(reader.line_num) + ' has ' + str(len(row)) + ' columns. Look at your mess:<br><br><b>' + str(row) + '</b>'
          return redirect(url_for('show_error', msg=msg))
        else:
          buffer.append(row)

    # No file errors. Save job + calls to DB.
    job_record = {
      'auth_id': AUTH_ID,
      'auth_token': AUTH_TOKEN,
      'cps': CPS,
      'max_attempts': MAX_ATTEMPTS,
      'template': request.form['template'],
      'verify_phone': request.form['verify_phone'],
      'message': request.form['message'],
      'audio_url': request.form['audio'],
      'audio_order': order,
      'fire_dtime': fire_dtime,
      'status': 'pending'
    }
    
    client = pymongo.MongoClient('localhost',27017)
    db = client['wsf']
    job_id = db['call_jobs'].insert(job_record)
    job_id = str(job_id)
    logger.info('Job %s added to DB' % job_id)

    for row in buffer:
      call = {
        'job_id': job_id,
        'name': row[0],
        'to': row[1],
        'etw_status': row[2],
        'event_date': row[3],
        'office_notes': row[4],
        'status': 'not attempted',
        'attempts': 0
      }
      list_of_calls.append(call)

    db['calls'].insert(list_of_calls)
    logger.info('Calls added to DB for job %s' % job_id)

    calls = db['calls'].find({'job_id':job_id})
    job = db['call_jobs'].find_one({'_id':ObjectId(job_id)})

    return redirect(url_for('show_calls', job_id=job_id, calls=calls, job=job))

#-------------------------------------------------------------------
@app.route('/jobs')
def show_jobs():
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  jobs = db['call_jobs'].find().sort('fire_dtime',-1)

  return render_template('show_jobs.html', jobs=jobs)

#-------------------------------------------------------------------
@app.route('/jobs/<job_id>')
def show_calls(job_id): #sort_by=None, sort_order=None):
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']

  if 'sort_by' not in request.args:
    sort_by = 'name'
    sort_order = 1
  else:
    sort_by = request.args['sort_by']
    sort_order = int(request.args['sort_order'])
  
  calls = db['calls'].find({'job_id':job_id}).sort(sort_by, sort_order)
  job = db['call_jobs'].find_one({'_id':ObjectId(job_id)})

  sort_cols = [
    {'name': 1},
    {'to': 1},
    {'etw_status': 1},
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
      #col[sort_by] = col[sort_by] * -1

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
@app.route('/cancel/job/<job_id>')
def cancel_job(job_id):
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  db['call_jobs'].remove({'_id':ObjectId(job_id)})
  db['calls'].remove({'job_id':job_id})
  logger.info('Removed db.call_jobs and db.calls for %s' % job_id)

  jobs = db['call_jobs'].find()

  return redirect(url_for('show_jobs'))

#-------------------------------------------------------------------
@app.route('/cancel/call/<call_id>')
def cancel_call(call_id):
  job_id = request.args['job_id']
  client = pymongo.MongoClient('localhost',27017)
  db = client['wsf']
  db['calls'].remove({'_id':ObjectId(call_id)})
    


  return redirect(url_for('show_calls', job_id=job_id, sort_by=request.args['sort_by'], sort_order=request.args['sort_order']))

#-------------------------------------------------------------------
@app.route('/call/answer',methods=['POST','GET'])
def content():
  try:
    logger.debug('Call answered %s' % request.values.items())

    if request.form.get('Direction') == 'inbound':
      response = plivoxml.Response()
      return Response(str(response), mimetype='text/xml')

    request_uuid = request.form.get('RequestUUID')
    call_uuid = request.form.get('CallUUID')
    
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
    dt = parse(call['event_date'])
    date_str = dt.strftime('%A, %B %d')
    speak = ('Hi, this is a friendly reminder from the Winny Fred ' +
      'stewart association that your next empties to winn pickup date ' +
      'is ' + date_str + '. please have your empties out by 8am. ' +
      'To repeat this message press 1.'
    )
  
    logger.debug('%s Answered.' % call['to'])
   
    response = plivoxml.Response()
    response.addWait(length=1)
    response.addSpeak(body=speak)
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

    db['calls'].update(
        {'request_id':request_uuid}, 
        {'$set': {
            'status': call_status,
            'code': cause,
            'attempts': attempts
            }
        }
    )

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
    app.run(host='0.0.0.0', port=port)
