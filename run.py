'''run'''
import logging, os, time, sys, getopt
from os import environ, system
from flask import current_app, g, session
from flask_login import current_user
from detect import startup_msg, set_environ
from app import get_logger, db_client, create_app
from app.auth import load_user
from app.utils import bcolors, print_vars, inspector
from app.socketio import sio_server

log = get_logger('run')
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

    system('kill %1')
    system("ps aux | grep '/usr/bin/python -m celery' | awk '{print $2}' | xargs kill -9")
    system("ps aux | grep '/usr/bin/python /usr/local/bin/celery beat' | awk '{print $2}' | xargs kill -9")

#-------------------------------------------------------------------------------
def start_celery(beat=True):
    '''Start celery worker/beat as child processes.
    IMPORTANT: If started from outside bravo or with --detach option, will NOT
    have os.environ vars
    '''

    if not beat:
        environ['BRV_BEAT'] = 'False'
    system('celery -A app.tasks.celery -n bravo worker -f logs/worker.log -l INFO &')
    if beat:
        system('celery -A app.tasks.celery beat -f logs/beat.log -l INFO &')

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

    log.info('server starting...')

    set_environ(app)
    sio_server.init_app(app, async_mode='eventlet', message_queue='amqp://')

    kill_celery()
    time.sleep(1)
    start_celery(beat=environ.get('BRV_BEAT'))

    startup_msg(app)

    log.info('server ready!')

    sio_server.run(
        app,
        port=app.config['LOCAL_PORT'],
        log_output=False,
        use_reloader=False)

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
