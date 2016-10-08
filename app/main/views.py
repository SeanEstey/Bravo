import json
import twilio.twiml
import time
import requests
from datetime import datetime, date
import flask
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask.ext.login import login_required, current_user
from bson.objectid import ObjectId
import logging

# Setup Blueprint
main = Blueprint('main', __name__, url_prefix='/')

# Import modules and objects

from app import utils
from app import gsheets
from app import tasks
from app.main import auth
from app.main import log
from app.main import receipts
from app.notify.views import on_email_status as notify_on_email_status

# Import objects
from app import db, app, socketio

# Get logger
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@main.route('')
def landing_page():
    return redirect(url_for('notify.view_event_list'))

#-------------------------------------------------------------------------------
@main.route('login', methods=['GET','POST'])
def user_login():
    return auth.login()

#-------------------------------------------------------------------------------
@main.route('logout', methods=['GET'])
def user_logout():
    auth.logout()
    return redirect(app.config['PUB_URL'])

#-------------------------------------------------------------------------------
@main.route('log')
@login_required
def view_log():
    lines = log.get_tail(app.config['LOG_PATH'] + 'info.log', app.config['LOG_LINES'])

    return render_template('views/log.html', lines=lines)

#-------------------------------------------------------------------------------
@main.route('admin')
@login_required
def view_admin():
    user = db['users'].find_one({'user': current_user.username})
    agency = db['users'].find_one({'user': current_user.username})['agency']

    if user['admin'] == True:
        settings = db['agencies'].find_one({'name':agency}, {'_id':0, 'google.oauth':0})
        settings_html = utils.dict_to_html_table(settings)
    else:
        settings_html = ''

    return render_template('views/admin.html', agency_config=settings_html)

#-------------------------------------------------------------------------------
@main.route('sendsocket', methods=['GET'])
def request_send_socket():
    name = request.args.get('name').encode('utf-8')
    data = request.args.get('data').encode('utf-8')
    socketio.emit(name, data)
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('booking', methods=['GET'])
@login_required
def show_booking():
    agency = db['users'].find_one({'user': current_user.username})['agency']
    return render_template('views/booking.html', agency=agency)



#-------------------------------------------------------------------------------
@main.route('receipts/process', methods=['POST'])
def process_receipts():
    '''Data sent from Routes worksheet in Gift Importer (Google Sheet)
    @arg 'data': JSON array of dict objects with UDF and gift data
    @arg 'etapestry': JSON dict of etapestry info for PHP script
    '''

    logger.info('Process receipts request received')

    entries = json.loads(request.form['data'])
    etapestry = json.loads(request.form['etapestry'])

    # Start celery workers to run slow eTapestry API calls
    r = tasks.process_receipts.apply_async(
      args=(entries, etapestry),
      queue=app.config['DB']
    )

    #logger.info('Celery process_receipts task: %s', r.__dict__)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('email/send', methods=['POST'])
def _send_email():
    '''Can be collection receipt from gsheets.process_receipts, reminder email,
    or welcome letter from Google Sheets.
    Required fields: 'agency', 'recipient', 'template', 'subject', and 'data'
    Required fields for updating Google Sheets:
    'data': {'from':{ 'worksheet','row','upload_status'}}
    Returns mailgun_id of email
    '''
    args = request.get_json(force=True)

    logger.debug('/email/send: "%s"', args)

    for key in ['template', 'subject', 'recipient']:
        if key not in args:
            e = '/email/send: missing one or more required fields'
            logger.error(e)
            return flask.Response(response=e, status=500, mimetype='application/json')

    try:
        html = render_template(args['template'], data=args['data'])
    except Exception as e:
        msg = '/email/send: invalid email template'
        logger.error('%s: %s', msg, str(e))
        return flask.Response(response=e, status=500, mimetype='application/json')

    mailgun = db['agencies'].find_one({'name':args['agency']})['mailgun']

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
        logger.error(str(e))
        return flask.Response(response=e, status=500, mimetype='application/json')

    if r.status_code != 200:
        err = 'Invalid email address "' + args['recipient'] + '": ' + json.loads(r.text)['message']

        logger.error(err)

        gsheets.create_rfu(args['agency'], err)

        return flask.Response(response=str(r), status=500, mimetype='application/json')

    db['emails'].insert({
        'agency': args['agency'],
        'mid': json.loads(r.text)['id'],
        'status': 'queued',
        'on_status': args['data']['from']
    })

    logger.debug('Queued email to ' + args['recipient'])

    return json.loads(r.text)['id']

#-------------------------------------------------------------------------------
@main.route('email/<agency>/unsubscribe', methods=['GET'])
def email_unsubscribe(agency):

    if request.args.get('email'):
        msg = 'Contributor ' + request.args.get('email') + ' has requested to \
              unsubscribe from emails. Please contact to see if they want \
              to cancel the entire service.'

        if agency == 'wsf':
            to = 'emptiestowinn@wsaf.ca'
        elif agency == 'vec':
            to = 'recycle@vecova.ca'

        mailgun = db['agencies'].find_one({})['mailgun']

        try:
            r = requests.post(
              'https://api.mailgun.net/v3/' + 'bravoweb.ca' + '/messages',
              auth=('api', mailgun['api_key']),
              data={
                'from': mailgun['from'],
                'to': to,
                'subject': 'Unsubscribe Request',
                'html': msg
            })
        except requests.exceptions.RequestException as e:
            logger.error(str(e))
            return flask.Response(response=e, status=500, mimetype='application/json')

        return 'We have received your request to unsubscribe ' \
                + request.args.get('email') + ' If you wish \
                to cancel the service, please allow us to contact you once \
                more to arrange for retrieval of the Bag Buddy or other \
                collection materials provided to you. As a non-profit, \
                this allows us to spread out our costs.'
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('email/spam_complaint', methods=['POST'])
def email_spam_complaint():
    mmg = request.form['recipient']'received spam complaint'
    
    if request.form['domain'] == 'recycle.vecova.ca':
        agency = 'vec'
    elif request.form['domain'] == 'wsaf.ca':
        agency = 'wsf'

    try:
        gsheets.create_rfu(
            agency,
            "%s sent spam complaint" % request.form['recipient']
        )     
    except Exception as e:
        logger.error('create spam rfu: %s', str(e))
        return str(e)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('email/status',methods=['POST'])
def email_status():
    '''Relay for Mailgun webhooks. Can originate from reminder_msg, Signups
    sheet, or Route Importer sheet
    Guaranteed POST data: 'event', 'recipient', 'Message-Id'
    event param can be: 'delivered', 'bounced', or 'dropped'
    Optional POST data: 'code' (on dropped/bounced), 'error' (on bounced),
    'reason' (on dropped)
    '''

    logger.info('Email to %s %s',
      request.form['recipient'], request.form['event']
    )

    event = request.form['event']

    email = db['emails'].find_one_and_update(
      {'mid': request.form['Message-Id']},
      {'$set': { 'status': request.form['event']}}
    )

    import bson.json_util
    logger.debug('email: %s', bson.json_util.dumps(email))

    if email is None:
        return 'Mid not found'

    #------------- NEW CODE----------------

    # Do any special updates
    if email.get('type'):
        if email['type'] == 'notification':
            notify_on_email_status(request.form.to_dict())
            #return redirect(url_for('notify.on_email_status'))
            #notifications.on_email_status(request.form.to_dict())
        elif email['type'] == 'receipt':
            receipts.on_email_status(request.form.to_dict())
    # -----------------------------------
    # Signup welcomeor booking confirmation email?
    else:
        try:
            gsheets.update_entry(
              email['agency'],
              request.form['event'],
              email['on_status']
            )
        except Exception as e:
            logger.error("Error writing to Google Sheets: " + str(e))
            return 'Failed'

    #-----------------------------

    # Every email type gets an RFU created

    if event == 'dropped':
        msg = request.form['recipient'] + ' ' + event + ': '

        reason = request.form.get('reason')

        if reason == 'old':
            msg += 'Tried to deliver unsuccessfully for 8 hours'
        elif reason == 'hardfail':
            msg +=  'Can\'t deliver to previous invalid address'

        logger.info(msg)

        tasks.create_rfu.apply_async(
            args=(email['agency'], msg, ),
            queue=app.config['DB'])

    #socketio.emit('update_msg', {'id':str(msg['_id']), 'emails': request.form['event']})

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('call/nis', methods=['POST'])
def nis():
    logger.info('NIS!')

    record = request.get_json()

    try:
        gsheets.create_rfu(
          record['custom']['to'] + ' not in service',
          a_id=record['account_id'],
          block=record['custom']['block']
        )
    except Exception, e:
        logger.info('%s /call/nis' % request.values.items(), exc_info=True)
    return str(e)

#-------------------------------------------------------------------------------
@main.route('receive_signup', methods=['POST'])
def rec_signup():
    '''Forwarded signup submision from emptiestowinn.com
    Adds signup data to Bravo Sheets->Signups gsheet row
    '''

    try:
        tasks.add_signup.apply_async(
          args=(request.form.to_dict(),), # Must include comma
          queue=app.config['DB']
        )
    except Exception as e:
        time.sleep(1)
        logger.info('/receive_signup: %s', str(e), exc_info=True)
        logger.info('Retrying...')
        tasks.add_signup.apply_async(
          args=(request.form.to_dict(),),
          queue=app.config['DB']
        )
        return str(e)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('render_receipt', methods=['POST'])
def render_receipt_body():
    try:
        args = request.get_json(force=True)

        return render_template(
          args['template'],
          to = args['data'].get('account').get('email'),
          account = args['data'].get('account'),
          entry = args['data'].get('entry'),
          history = args['data'].get('history'),
          data=args['data'] # remove this after testing
        )
    except Exception as e:
        logger.error('render_receipt: %s ', str(e))
        return 'Error'


