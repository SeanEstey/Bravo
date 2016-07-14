import json
import twilio.twiml
import time
import requests
import datetime
from flask import request, Response, render_template, redirect
from flask.ext.login import login_required, current_user
from bson.objectid import ObjectId

# Import Application objects
from app import app, db, socketio

# Import methods
from utils import send_mailgun_email
from log import get_tail
from auth import login, logout
from routing import get_completed_route, start_job

import reminders
import receipts
import gsheets
import scheduler

#-------------------------------------------------------------------------------
@app.route('/', methods=['GET'])
@login_required
def view_jobs():
    return render_template(
      'views/job_list.html',
      title=None,
      jobs=reminders.get_jobs(request.args.values())
    )

#-------------------------------------------------------------------------------
@app.route('/login', methods=['GET','POST'])
def user_login():
    return login()


#-------------------------------------------------------------------------------
@app.route('/logout', methods=['GET'])
def user_logout():
    logout()
    return redirect(app.config['PUB_URL'])

#-------------------------------------------------------------------------------
@app.route('/log')
@login_required
def view_log():
    lines = get_tail(app.config['LOG_PATH'] + 'info.log', app.config['LOG_LINES'])

    return render_template('views/log.html', lines=lines)

#-------------------------------------------------------------------------------
@app.route('/admin')
@login_required
def view_admin():
    return render_template('views/admin.html')

#-------------------------------------------------------------------------------
@app.route('/sendsocket', methods=['GET'])
def request_send_socket():
    name = request.args.get('name').encode('utf-8')
    data = request.args.get('data').encode('utf-8')
    socketio.emit(name, data)
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/routing/get_route/<job_id>', methods=['GET'])
def get_route(job_id):
    return json.dumps(get_completed_route(job_id))

#-------------------------------------------------------------------------------
@app.route('/routing/start_job', methods=['POST'])
def get_routing_job_id():
    app.logger.info('Routing Block %s...', request.form['block'])

    return start_job(
            request.form['block'],
            request.form['driver'],
            request.form['date'],
            request.form['start_address'],
            request.form['end_address'],
            json.loads(request.form["etapestry_id"]),
            request.form['min_per_stop'],
            request.form['shift_start'])

#-------------------------------------------------------------------------------
@app.route('/reminders/new')
@login_required
def new_job():
    agency = db['users'].find_one({'user': current_user.username})['agency']

    try:
        with open('templates/schemas/'+agency+'.json') as json_file:
          templates = json.load(json_file)['reminders']
    except Exception as e:
        app.logger.error("Couldn't open json schemas file")
        return "Error"

    return render_template('views/new_job.html', templates=templates, title=app.config['TITLE'])

#-------------------------------------------------------------------------------
@app.route('/reminders/submit_job', methods=['POST'])
@login_required
def submit_job():
    try:
        r = reminders.submit_job(request.form.to_dict(), request.files['call_list'])
        return Response(response=json.dumps(r), status=200, mimetype='application/json')
    except Exception as e:
        app.logger.error('submit_job: %s', str(e))
        return False

#-------------------------------------------------------------------------------
@app.route('/reminders/recordaudio', methods=['GET', 'POST'])
def record_msg():
    return reminders.record_audio()

#-------------------------------------------------------------------------------
@app.route('/reminders/<job_id>')
@login_required
def view_job(job_id):
    sort_by = 'name'
    reminders = db['reminders'].find({'job_id':ObjectId(job_id)}).sort(sort_by, 1)
    job = db['jobs'].find_one({'_id':ObjectId(job_id)})

    return render_template(
        'views/job.html',
        title=app.config['TITLE'],
        reminders=reminders,
        job_id=job_id,
        job=job,
        template=job['schema']['import_fields']
    )

#-------------------------------------------------------------------------------
@app.route('/reminders/<job_id>/cancel')
@login_required
def cancel_job(job_id):
    reminders.cancel_job(job_id)
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/reminders/<job_id>/reset')
@login_required
def reset_job(job_id):
    reminders.reset_job(job_id)
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/reminders/<job_id>/send_emails')
@login_required
def send_emails(job_id):
    reminders.send_emails.apply_async(
            (job_id.encode('utf-8'),),
            queue=app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/reminders/<job_id>/send_calls')
@login_required
def send_calls(job_id):
    job_id = job_id.encode('utf-8')

    # Start new job
    db['jobs'].update_one(
      {'_id': ObjectId(job_id)},
      {'$set': {
        "status": "in-progress",
        "voice.started_at": datetime.datetime.now()}})

    reminders.send_calls.apply_async(
            args=(job_id, ),
            queue=app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/reminders/<job_id>/complete')
@login_required
def job_complete(job_id):
    '''Email job summary, update job status'''

    app.logger.info('Job [ID %s] complete!', job_id)

    # TODO: Send socket to web app to display completed status

    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/reminders/<job_id>/<reminder_id>/remove', methods=['POST'])
@login_required
def rmv_msg(job_id, reminder_id):
    reminders.rmv_msg(job_id, reminder_id)
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/reminders/<reminder_id>/edit', methods=['POST'])
@login_required
def edit_msg(reminder_id):
    reminders.edit_msg(reminder_id, request.form.items())
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/reminders/<job_id>/<msg_id>/cancel_pickup', methods=['GET'])
def no_pickup(job_id, msg_id):
    '''Script run via reminder email'''

    reminders.cancel_pickup.apply_async((msg_id,), queue=app.config['DB'])
    return 'Thank You'

#-------------------------------------------------------------------------------
@app.route('/reminders/call.xml',methods=['POST'])
def call_xml():
    '''Twilio TwiML Voice Request
    Returns twilio.twiml.Response obj
    '''

    try:
        app.logger.debug('call.xml request values: %s', request.values.to_dict())

        r = reminders.get_voice_response(request.values.to_dict())

        if type(r) is twilio.twiml.Response:
            return Response(str(r), mimetype='text/xml')

        # Returned .html template file for rendering

        reminder = db['reminders'].find_one({'voice.sid': request.form['CallSid']})

        html = render_template(
            r,
            reminder=json.loads(reminders.bson_to_json(reminder))
        )

        html = html.replace("\n", "")
        html = html.replace("  ", "")
        app.logger.debug('speak template: %s', html)

        db['reminders'].update({'_id':reminder['_id']},{'$set':{'voice.speak':html}})

        response = twilio.twiml.Response()
        response.say(html, voice='alice')

        # ONLY FOR REMINDER MESSAGES
        response.gather(numDigits=1, action='/reminders/call.xml', method='POST')

        return Response(str(response), mimetype='text/xml')
    except Exception as e:
        app.logger.error('call.xml: %s', str(e))
        return False

#-------------------------------------------------------------------------------
@app.route('/get_speak', methods=['POST'])
def get_template():
    html = render_template(
        request.form['template'],
        reminder=json.loads(request.form['reminder'])
    )

    app.logger.debug('returning speak')

    return html.replace("\n", "")

#-------------------------------------------------------------------------------
@app.route('/reminders/call_event',methods=['POST','GET'])
def call_event():
    '''Twilio callback'''

    reminders.call_event(request.form.to_dict())
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/receipts/process', methods=['POST'])
def process_receipts():
    '''Data sent from Routes worksheet in Gift Importer (Google Sheet)
    @arg 'data': JSON array of dict objects with UDF and gift data
    @arg 'etapestry': JSON dict of etapestry info for PHP script
    '''

    app.logger.info('Process receipts request received')

    entries = json.loads(request.form['data'])
    etapestry = json.loads(request.form['etapestry'])

    # Start celery workers to run slow eTapestry API calls
    r = receipts.process.apply_async(
      args=(entries, etapestry),
      queue=app.config['DB']
    )

    #app.logger.info('Celery process_receipts task: %s', r.__dict__)

    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/email/send', methods=['POST'])
def send_email():
    '''Can be collection receipt from gsheets.process_receipts, reminder email,
    or welcome letter from Google Sheets.
    Required fields: 'agency', 'recipient', 'template', 'subject', and 'data'
    Required fields for updating Google Sheets:
    'data': {'from':{ 'worksheet','row','upload_status'}}
    Returns mailgun_id of email
    '''
    args = request.get_json(force=True)

    app.logger.debug('/email/send: "%s"', args)

    for key in ['template', 'subject', 'recipient']:
        if key not in args:
            e = '/email/send: missing one or more required fields'
            app.logger.error(e)
            return Response(response=e, status=500, mimetype='application/json')

    try:
        html = render_template(args['template'], data=args['data'])
    except Exception as e:
        msg = '/email/send: invalid email template'
        app.logger.error('%s: %s', msg, str(e))
        return Response(response=e, status=500, mimetype='application/json')

    mailgun = db['agencies'].find_one({'name':args['agency']})['mailgun']

    # TEMPORARY HACK DUE TO RECYCLE.VECOVA.CA AND SHAW DOMAIN ISSUE
    if args['agency'] == 'vec' and args['recipient'].find('shaw.ca') > -1:
        mailgun['domain'] = mailgun['alt_domain']

    try:
        r = requests.post(
          'https://api.mailgun.net/v3/' + mailgun['domain'] + '/messages',
          auth=('api', mailgun['api_key']),
          data={
            'from': mailgun['from'],
            'to': args['recipient'],
            'subject': args['subject'],
            'html': html
        })
    except requests.exceptions.RequestException as e:
        app.logger.error(str(e))
        return Response(response=e, status=500, mimetype='application/json')

    if r.status_code != 200:
        e = '/email/send: mailgun error: ' + r.text
        app.logger.error(e)
        return Response(response=e, status=500, mimetype='application/json')

    db['emails'].insert({
        'agency': args['agency'],
        'mid': json.loads(r.text)['id'],
        'status': 'queued',
        'on_status_update': args['data']['from']
    })

    app.logger.info('Queued email to ' + args['recipient'])

    return json.loads(r.text)['id']

#-------------------------------------------------------------------------------
@app.route('/email/unsubscribe', methods=['GET'])
def email_unsubscribe():
    if request.args.get('email'):
        msg = 'Contributor ' + request.args.get('email') + ' has requested to \
              unsubscribe from emails. Please contact to see if they want \
              to cancel the entire service.'

        mailgun = db['agencies'].find_one({})['mailgun']

        try:
            r = requests.post(
              'https://api.mailgun.net/v3/' + 'bravoweb.ca' + '/messages',
              auth=('api', mailgun['api_key']),
              data={
                'from': mailgun['from'],
                'to': ['sestey@vecova.ca', 'emptiestowinn@wsaf.ca'],
                'subject': 'Unsubscribe Request',
                'html': msg
            })
        except requests.exceptions.RequestException as e:
            app.logger.error(str(e))
            return Response(response=e, status=500, mimetype='application/json')

        return 'We have received your request to unsubscribe ' \
                + request.args.get('email') + ' If you wish \
                to cancel the service, please allow us to contact you once \
                more to arrange for retrieval of the Bag Buddy or other \
                collection materials provided to you. As a non-profit, \
                this allows us to spread out our costs.'
    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/email/spam_complaint', methods=['POST'])
def email_spam_complaint():
    m = 'received spam complaint'

    try:
        gsheets.create_rfu(request.form['recipient'] + m)
    except Exception, e:
        app.logger.error('%s' % request.values.items(), exc_info=True)
        return str(e)

    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/email/status',methods=['POST'])
def email_status():
    '''Relay for Mailgun webhooks. Can originate from reminder_msg, Signups
    sheet, or Route Importer sheet
    Guaranteed POST data: 'event', 'recipient', 'Message-Id'
    event param can be: 'delivered', 'bounced', or 'dropped'
    Optional POST data: 'code' (on dropped/bounced), 'error' (on bounced),
    'reason' (on dropped)
    '''

    app.logger.info('Email to %s %s',
      request.form['recipient'], request.form['event']
    )

    event = request.form['event']

    email = db['emails'].find_one_and_update(
      {'mid': request.form['Message-Id']},
      {'$set': { 'status': request.form['event']}}
    )

    if email is None or 'on_status_update' not in email:
        return 'No record to update'

    if event == 'dropped':
        gsheets.create_rfu.apply_async(
            args=(email['agency'], request.form['recipient'] + ' ' + event, ),
            queue=app.config['DB'])

    if 'worksheet' in email['on_status_update']:
        # Update Google Sheets
        try:
            gsheets.update_entry(
              email['agency'],
              request.form['event'],
              email['on_status_update']
            )
        except Exception as e:
            app.logger.error("Error writing to Google Sheets: " + str(e))
            return 'Failed'

    elif 'reminder_id' in email['on_status_update']:
        # Update Reminder record
        db['reminders'].update_one(
          {'_id': ObjectId(email['on_status_update']['reminder_id'])},
          {'$set':{
            "email.status": request.form['event'],
            "email.code": request.form.get('code'),
            "email.reason": request.form.get('reason'),
            "email.error": request.form.get('error')
          }}
        )

    #socketio.emit('update_msg', {'id':str(msg['_id']), 'emails': request.form['event']})

    return 'OK'

#-------------------------------------------------------------------------------
@app.route('/get_np', methods=['GET'])
def get_romorrow_accounts():
    scheduler.find_nps_in_schedule.apply_async(queue=app.config['DB'])
    return 'Celery process started...'

#-------------------------------------------------------------------------------
@app.route('/call/nis', methods=['POST'])
def nis():
    app.logger.info('NIS!')

    record = request.get_json()

    try:
        gsheets.create_rfu(
          record['custom']['to'] + ' not in service',
          account_number=record['account_id'],
          block=record['custom']['block']
        )
    except Exception, e:
        app.logger.info('%s /call/nis' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
@app.route('/receive_signup', methods=['POST'])
def rec_signup():
    '''Forwarded signup submision from emptiestowinn.com
    Adds signup data to Bravo Sheets->Signups gsheet row
    '''

    app.logger.info('New signup received: %s %s',
      request.form.get('first_name'),
      request.form.get('last_name')
    )

    try:
        gsheets.add_signup.apply_async(
          args=(request.form.to_dict(),), # Must include comma
          queue=app.config['DB']
        )
    except Exception as e:
        time.sleep(1)
        app.logger.info('/receive_signup: %s', str(e), exc_info=True)
        app.logger.info('Retrying...')
        gsheets.add_signup.apply_async(
          args=(request.form.to_dict(),),
          queue=app.config['DB']
        )
        return str(e)

    return 'OK'
