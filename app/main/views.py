'''app.main.views'''

import json
import time
import requests
from datetime import datetime, date
from flask import g, request, render_template, redirect, url_for, current_app
from flask_login import login_required, current_user
from flask_socketio import SocketIO, emit
from bson.objectid import ObjectId
import logging

from . import main
from . import log, receipts
from .. import utils, html, gsheets
from app.notify import notifications
from .. import db
logger = logging.getLogger(__name__)


# ------------ Stuff TODO ----------------------
# TODO: add view endpoint awaiting return value from send_receipts task
# http://blog.miguelgrinberg.com/post/using-celery-with-flask


#-------------------------------------------------------------------------------
@main.route('/')
def landing_page():
    #return 'LANDING PAGE'
    return redirect(url_for('notify.view_event_list'))

#-------------------------------------------------------------------------------
@main.route('/log')
@login_required
def view_log():
    lines = log.get_tail(current_app.config['LOG_PATH'] + 'info.log', current_app.config['LOG_LINES'])

    return render_template('views/log.html', lines=lines)

#-------------------------------------------------------------------------------
@main.route('/admin')
@login_required
def view_admin():
    user = db['users'].find_one({'user': current_user.username})
    agency = db['users'].find_one({'user': current_user.username})['agency']

    if user['admin'] == True:
        settings = db['agencies'].find_one({'name':agency}, {'_id':0, 'google.oauth':0})
        settings_html = html.to_table(settings)
    else:
        settings_html = ''

    return render_template('views/admin.html', agency_config=settings_html)

#-------------------------------------------------------------------------------
@main.route('/booking', methods=['GET'])
@login_required
def show_booking():
    agency = db['users'].find_one({'user': current_user.username})['agency']
    return render_template('views/booking.html', agency=agency)

#-------------------------------------------------------------------------------
@main.route('/receipts/process', methods=['POST'])
def process_receipts():
    '''Data sent from Routes worksheet in Gift Importer (Google Sheet)
    @arg 'data': JSON array of dict objects with UDF and gift data
    @arg 'etapestry': JSON dict of etapestry info for PHP script
    '''

    logger.info('Process receipts request received')

    entries = json.loads(request.form['data'])
    etapestry = json.loads(request.form['etapestry'])

    from .. import tasks
    # Start celery workers to run slow eTapestry API calls
    r = tasks.send_receipts.apply_async(
      args=[entries, etapestry],
      queue=current_app.config['DB']
    )

    #logger.info('Celery process_receipts task: %s', r.__dict__)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/send', methods=['POST'])
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
@main.route('/email/<agency>/unsubscribe', methods=['GET'])
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
@main.route('/email/spam_complaint', methods=['POST'])
def email_spam_complaint():

    if request.form['domain'] == 'recycle.vecova.ca':
        agency = 'vec'
    elif request.form['domain'] == 'wsaf.ca':
        agency = 'wsf'

    try:
        gsheets.create_rfu(
            agency,
            "%s sent spam complaint" % request.form['recipient'])
    except Exception as e:
        logger.error('create spam rfu: %s', str(e))
        return str(e)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/delivered',methods=['POST'])
def on_email_delivered():
    '''Relay for Mailgun webhook'''

    # TODO: Cannot manually set webhook URL.
    # Route any notify.emails to email modulee
    
    logger.info('Email to %s %s',
      request.form['recipient'], request.form['event']
    )

    event = request.form['event']

    email = db['emails'].find_one_and_update(
      {'mid': request.form['Message-Id']},
      {'$set': { 'status': request.form['event']}}
    )

    if email is None:
        return 'Mid not found'

    # Route to specialized handlers

    if email.get('type'):
        if email['type'] == 'notification':
            notifications.on_email_status(request.form.to_dict())
        elif email['type'] == 'receipt':
            receipts.on_email_status(request.form.to_dict())
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

    #emit('update_msg', {'id':str(msg['_id']), 'emails': request.form['event']})

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/dropped', methods=['POST'])
def on_email_dropped():
    '''Relay for Mailgun webhook
    POST args: 'code', 'error', 'reason'
    '''

    logger.debug(request.values.to_dict())

    event = request.form['event']

    logger.info('Email to %s %s', request.form['recipient'], event)

    email = db['emails'].find_one_and_update(
      {'mid': request.form['Message-Id']},
      {'$set': { 'status': event}}
    )

    #if email is None:
    #    return 'Mid not found'

    msg = request.form['recipient'] + ' ' + event + ': '

    reason = request.form.get('reason')

    msg = '%s %s. reason: %s. ' % (request.form['recipient'], event, request.form['reason'])
    logger.info(msg)

    # TEST CODE ONLY
    email = {'agency':'vec'}

    from .. import tasks
    tasks.rfu.apply_async(
        args=[
            email['agency'],
            msg + request.form.get('description')],
        kwargs={'_date': date.today().strftime('%-m/%-d/%Y')},
        queue=current_app.config['DB']
    )

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/receive_signup', methods=['POST'])
def rec_signup():
    '''Forwarded signup submision from emptiestowinn.com
    Adds signup data to Bravo Sheets->Signups gsheet row
    '''

    from .. import tasks
    try:
        tasks.add_signup.apply_async(
          args=(request.form.to_dict(),), # Must include comma
          queue=current_app.config['DB']
        )
    except Exception as e:
        time.sleep(1)
        logger.info('/receive_signup: %s', str(e), exc_info=True)
        logger.info('Retrying...')
        tasks.add_signup.apply_async(
          args=(request.form.to_dict(),),
          queue=current_app.config['DB']
        )
        return str(e)

    return 'OK'

@main.route('/secret_run_non_par', methods=['GET'])
def run_non_par():
    from .. import tasks
    tasks.find_non_participants.apply_async(queue=current_app.config['DB'])
    return 'OK'

