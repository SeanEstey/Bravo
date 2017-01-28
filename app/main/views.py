'''app.main.views'''
import logging, json, time
from flask import g, request, render_template, redirect, url_for, jsonify, Response
from flask_login import login_required
from .. import get_keys, html
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
@main.route('/email/delivered',methods=['POST'])
def on_delivered():
    '''Mailgun webhook
    '''

    log.debug(json.dumps(request.values.to_dict(), indent=4))

    type_ = request.form.get('type')
    agcy = request.form.get('agcy')

    if not type_:
        log.error('no v:type set. cannot route to delivered handler')
        return 'failed'

    if type_ == 'receipt':
        receipts.on_delivered(agcy)
    elif type_ == 'signup':
        signups.on_delivered(agcy)
    elif type_ == 'notific':
        from app.notify import email
        email.on_delivered()
    elif type_ == 'confirmation':
        book.on_delivered(agcy)

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/dropped', methods=['POST'])
def on_dropped():
    '''Mailgun webhook
    '''

    log.debug(json.dumps(request.values.to_dict(), indent=4))

    type_ = request.form.get('type')
    agcy = request.form.get('agcy')

    if not type_:
        log.error('no v:type set. cannot route to delivered handler')
        return 'failed'

    if type_ == 'receipt':
        receipts.on_dropped(agcy)
    elif type_ == 'signup':
        signups.on_dropped(agcy)
    elif type_ == 'notific':
        email.on_dropped()

    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/<agcy>/unsub', methods=['GET'])
def on_unsub(agcy):
    '''Mailgun webhook
    '''

    return donors.unsubscribe(agcy)

#-------------------------------------------------------------------------------
@main.route('/email/spam', methods=['POST'])
def on_spam():
    '''Mailgun webhook
    '''

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
@main.route('/receipts/process', methods=['POST'])
def send_receipts_():
    send_receipts.delay(request.form['entries'], etap=request.form['etapestry'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/signups/welcome', methods=['POST'])
def send_welcome():
    return signups.send_welcome()

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
