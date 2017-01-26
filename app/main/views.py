'''app.main.views'''
import logging, json, os, time, requests
from flask import g, request, render_template, redirect, url_for, jsonify, Response
from flask_login import login_required
from .. import get_keys, utils, html, gsheets, mailgun
from . import main, receipts, signups
from .tasks import create_rfu, send_receipts, add_gsheets_signup
from app.notify import admin
from app.booker import book
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@main.route('/')
def landing_page():
    return redirect(url_for('notify.view_event_list'))

#-------------------------------------------------------------------------------
@main.route('/admin')
@login_required
def view_admin():
    if g.user.admin == True:
        settings = get_keys()
        settings.pop('_id')
        settings['google'].pop('oauth')
        settings_html = html.to_div('', settings)
    else:
        settings_html = ''

    return render_template('views/admin.html', agency_config=settings_html)

#-------------------------------------------------------------------------------
@main.route('/update_agency_conf', methods=['POST'])
@login_required
def update_agency_conf():
    admin.update_agency_conf()
    return jsonify({'status':'success'})

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

    log.debug('/email/send: "%s"', args)

    for key in ['template', 'subject', 'recipient']:
        if key not in args:
            e = '/email/send: missing one or more required fields'
            log.error(e)
            return Response(response=e, status=500, mimetype='application/json')

    try:
        html = render_template(
            args['template'],
            data=args['data'],
            http_host= os.environ.get('BRAVO_HTTP_HOST')
        )
    except Exception as e:
        msg = '/email/send: invalid email template'
        log.error('%s: %s', msg, str(e))
        return Response(response=e, status=500, mimetype='application/json')

    try:
        mid = mailgun.send(
            args['recipient'], args['subject'], html, get_keys('mailgun'),
            v={'type':args.get('type')}
        )
    except Exception as e:
        log.error('could not email %s. %s', args['recipient'], str(e))
        create_rfu.delay(
            args['agency'], str(e))
        return Response(response=str(e), status=500, mimetype='application/json')
    else:
        g.db.emails.insert_one({
            'agency': args['agency'],
            'mid': mid,
            'type': args.get('type'),
            'on_status': {
                'update': args['data'].get('from')
                }
        })

    log.debug('Queued email to ' + args['recipient'])

    return mid

#-------------------------------------------------------------------------------
@main.route('/email/<agency>/unsubscribe', methods=['GET'])
def email_unsubscribe(agency):

    if request.args.get('email'):
        msg = 'Contributor ' + request.args.get('email') + ' has requested to \
              unsubscribe from emails. Please contact to see if they want \
              to cancel the entire service.'

        conf = g.db.agencies.find_one({'name':agency})['mailgun']

        try:
            r = requests.post(
              'https://api.mailgun.net/v3/' + 'bravoweb.ca' + '/messages',
              auth=('api', conf['api_key']),
              data={
                'from': conf['from'],
                'to': conf['from'],
                'subject': 'Unsubscribe Request',
                'html': msg
            })
        except requests.exceptions.RequestException as e:
            log.error(str(e))
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
        create_rfu.delay(
            agency,
            "%s sent spam complaint" % request.form['recipient'])
    except Exception as e:
        log.error('create spam rfu: %s', str(e))
        return str(e)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/delivered',methods=['POST'])
def on_email_delivered():
    '''Mailgun webhook. Route to appropriate handler'''

    log.debug(json.dumps(request.values.to_dict(), indent=4))

    if not request.form.get('my-custom-data'):
        return 'Unknown type'

    v = json.loads(request.form['my-custom-data'])

    if v.get('type') == 'receipt':
        receipts.on_delivered()
    elif v.get('type') == 'signup':
        signups.on_email_delivered()
    elif v.get('type') == 'notific':
        from app.notify import email
        email.on_delivered()
    elif v.get('type') == 'confirmation':
        book.on_delivered()

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/dropped', methods=['POST'])
def on_email_dropped():
    '''Mailgun webhook. Route to appropriate handler'''

    log.debug(json.dumps(request.values.to_dict(), indent=4))

    if not request.form.get('my-custom-data'):
        return 'Unknown type'

    v = json.loads(request.form['my-custom-data'])

    if v.get('type') == 'receipt':
        receipts.on_dropped()
    elif v.get('type') == 'signup':
        signups.on_email_dropped()
    elif v.get('type') == 'notific':
        email.on_dropped()

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/receive_signup', methods=['POST'])
def rec_signup():
    '''Forwarded signup submision from emptiestowinn.com
    Adds signup data to Bravo Sheets->Signups gsheet row
    '''

    try:
        add_gsheets_signup.delay(args=(request.form.to_dict()))
    except Exception as e:
        time.sleep(1)
        log.info('/receive_signup: %s', str(e), exc_info=True)
        log.info('Retrying...')
        add_gsheets_signup.delay(args=(request.form.to_dict()))
        return str(e)

    return 'OK'
