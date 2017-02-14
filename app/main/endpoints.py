'''app.main.endpoints'''
import json, logging, time
from flask import jsonify, request
from app import get_logger
from app.mailgun import dump
from app.booker import book
from . import donors, main, receipts, signups
from .tasks import create_rfu
log = get_logger('main.endpt')

#-------------------------------------------------------------------------------
@main.route('/email/delivered', methods=['POST'])
def on_delivered():
    # Mailgun webhook

    #log.debug('%s delivered', request.form['recipient'])
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
    # Mailgun webhook

    #log.debug(json.dumps(request.values.to_dict(), indent=4))
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
