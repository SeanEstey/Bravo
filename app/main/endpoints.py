'''app.main.endpoints'''
import gc, json, logging, time, os
from flask import g, request
from flask_login import login_required
from app import colors as c
from app.booker import book
from . import main # Blueprint
from . import donors, receipts, signups
from .tasks import create_rfu
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@main.route('/health_check', methods=['POST'])
def _health_chk():

    from app.lib.utils import mem_check

    g.group = 'vec'
    mem = mem_check()

    if mem['free'] < 350:
        log.debug('Low memory. %s/%s. Running garbage collection...',
            mem['free'], mem['total'])

        # Return mem back to OS for celery child processes
        gc.collect()

        # Clear cache
        os.system('sudo sysctl -w vm.drop_caches=3')
        os.system('sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches')

        mem2 = mem_check()
        log.debug('Freed %s mb', mem2['free'] - mem['free'])

        if mem2['free'] < 350:
            log.warning('Warning: low memory! 250mb recommended (%s/%s)',
                mem2['free'], mem['total'])
    else:
        log.debug('Health OK. Free=%s', mem['free'])

    return 'OK'

#-------------------------------------------------------------------------------
@login_required
@main.route('/update_calendar', methods=['GET'])
def update_cal():
    from app.main.tasks import update_calendar
    update_calendar.delay(group=g.group)
    return 'success'

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
    g.group = request.form.get('group') or request.form.get('agcy')

    if not webhook:
        log.debug('%swebhook "type" not set. cannot route to handler%s',
            c.RED,c.ENDC)
        return 'failed'
    if webhook == 'receipt':
        receipts.on_delivered(g.group)
    elif webhook == 'signup':
        signups.on_delivered(g.group)
    elif webhook == 'notific':
        from app.notify import email
        email.on_delivered()
    elif webhook == 'booking':
        book.on_delivered(g.group)
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
    g.group = request.form.get('group')

    if not webhook:
        log.debug('%swebhook "type" not set. cannot route to handler%s', c.RED, c.ENDC)
        log.debug(request.form.to_dict())
        return 'failed'
    if webhook == 'receipt':
        receipts.on_dropped(g.group)
    elif webhook == 'signup':
        signups.on_dropped(g.group)
    elif webhook == 'notific':
        from app.notify import email
        email.on_dropped()
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/email/<group>/unsub', methods=['GET','POST'])
def on_unsub(group):
    # Mailgun webhook
    return donors.unsubscribe(group)

#-------------------------------------------------------------------------------
@main.route('/email/spam', methods=['POST'])
def on_spam():
    # Mailgun webhook
    group = 'vec' if request.form['domain'] == 'recycle.vecova.ca' else 'wsf'
    create_rfu.delay(group, "%s sent spam complaint" % request.form['recipient'])
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
