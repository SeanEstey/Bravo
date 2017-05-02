'''run'''
import os, time, sys, getopt
from os import environ, system
from flask import current_app, g, session
from flask_login import current_user
from detect import startup_msg, set_environ
from app import db_client, create_app
from app.auth import load_user
from app.lib.utils import print_vars, inspector
from app.main.socketio import sio_server
from app.lib.loggy import Loggy
log = Loggy('app')
app = create_app('app')

#-------------------------------------------------------------------------------
@app.before_request
def do_setup():
    session.permanent = True
    g.db = db_client['bravo']

    if session.get('user_id'):
        g.user = load_user(session['user_id'])
        g.app = current_app

#-------------------------------------------------------------------------------
@app.after_request
def do_teardown(response):
    return response

#-------------------------------------------------------------------------------
def kill_celery():
    '''Kill any existing worker/beat processes, start new worker
    '''

    system("ps aux | "\
           "grep '/usr/bin/python /usr/local/bin/celery' | "\
           "awk '{print $2}' |"\
           "sudo xargs kill -9")

#-------------------------------------------------------------------------------
def start_celery(beat=True):
    '''Start celery worker/beat as child processes.
    IMPORTANT: If started from outside bravo or with --detach option, will NOT
    have os.environ vars
    '''

    if not beat:
        environ['BRV_BEAT'] = 'False'
    else:
        system('celery -A app.tasks.celery beat -f logs/celery.log -l INFO &')
    system('celery -A app.tasks.celery -n bravo worker -f logs/celery.log -l INFO &')

#-------------------------------------------------------------------------------
def main(argv):
    try:
        opts, args = getopt.getopt(argv,"cds", ['celerybeat', 'debug', 'sandbox'])
    except getopt.GetoptError:
        sys.exit(2)

    for opt, arg in opts:
        if opt in('-c', '--celerybeat'):
            environ['BRV_BEAT'] = 'True'
            beat = True
        elif opt in ('-d', '--debug'):
            app.config['DEBUG'] = True
        elif opt in ('-s', '--sandbox'):
            environ['BRV_SANDBOX'] = 'True'

    log.info('starting server...')

    set_environ(app)
    sio_server.init_app(app, async_mode='eventlet', message_queue='amqp://')

    kill_celery()
    time.sleep(1)
    start_celery(beat=bool(environ.get('BRV_BEAT')))

    startup_msg(app)

    log.info("she's ready, captain!")

    sio_server.run(
        app,
        port=app.config['LOCAL_PORT'],
        log_output=False,
        use_reloader=False)

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
