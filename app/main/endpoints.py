'''app.main.endpoints'''
import json, time
from flask import jsonify, request
from app.lib.loggy import Loggy, colors as c
from app.lib.mailgun import dump
from app.booker import book
from . import donors, main, receipts, signups
from .tasks import create_rfu
log = Loggy('main.endpt')

#-------------------------------------------------------------------------------
@main.route('/restart_worker', methods=['GET'])
def restart_worker():
    log.debug('restarting worker...')
    from run import kill_celery, start_celery
    log.debug('restarting worker...')
    kill_celery()
    time.sleep(1)
    start_celery()
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/delivered', methods=['POST'])
def on_delivered():
    '''Mailgun webhook
    '''

    webhook = request.form.get('type')
    agcy = request.form.get('agcy')

    if not webhook:
        log.debug('%swebhook "type" not set. cannot route to handler%s',
            c.RED,c.ENDC)
        log.debug(request.form.to_dict())
        return 'failed'
    if webhook == 'receipt':
        receipts.on_delivered(agcy)
    elif webhook == 'signup':
        signups.on_delivered(agcy)
    elif webhook == 'notific':
        from app.notify import email
        email.on_delivered()
    elif webhook == 'booking':
        book.on_delivered(agcy)
    else:
        log.debug('%sdelivered <%s> to %s%s',
            c.GRN, webhook, request.form['To'], c.ENDC)
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/dropped', methods=['POST'])
def on_dropped():
    '''Mailgun webhook
    '''

    webhook = request.form.get('type')
    agcy = request.form.get('agcy')

    if not webhook:
        log.debug('%swebhook "type" not set. cannot route to handler%s', c.RED, c.ENDC)
        log.debug(request.form.to_dict())
        return 'failed'
    if webhook == 'receipt':
        receipts.on_dropped(agcy)
    elif webhook == 'signup':
        signups.on_dropped(agcy)
    elif webhook == 'notific':
        from app.notify import email
        email.on_dropped()
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/<agcy>/unsub', methods=['GET','POST'])
def on_unsub(agcy):
    # Mailgun webhook
    return donors.unsubscribe(agcy)

#-------------------------------------------------------------------------------
@main.route('/email/spam', methods=['POST'])
def on_spam():
    # Mailgun webhook
    agcy = 'vec' if request.form['domain'] == 'recycle.vecova.ca' else 'wsf'
    create_rfu.delay(agcy, "%s sent spam complaint" % request.form['recipient'])
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

    from .tasks import add_gsheets_signup
    try:
        add_gsheets_signup.delay(args=(request.form.to_dict()))
    except Exception as e:
        time.sleep(1)
        log.info('/receive_signup: %s', str(e), exc_info=True)
        log.info('Retrying...')
        add_gsheets_signup.delay(args=(request.form.to_dict()))
        return str(e)
    return 'OK'
