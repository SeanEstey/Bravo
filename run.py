'''run'''
import logging, os, time, sys, getopt
from flask import current_app, g, session
from flask_login import current_user
from detect import startup_msg, set_environ
from app import db_client, create_app
from app.auth import load_user
from app.utils import bcolors, print_vars, inspector
from app.socketio import sio_server

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
def start_worker(beat=True):

    # Kill any existing worker/beat processes, start new worker

    os.system('kill %1')
    os.system("ps aux | grep '/usr/local/bin/celery beat' | awk '{print $2}' | xargs kill -9")
    os.system("ps aux | grep '/usr/local/bin/celery worker' | awk '{print $2}' | xargs kill -9")
    os.system('celery -A app.tasks.celery worker -n bravo -f logs/worker.log -l INFO --detach')

    # Start celery beat if option given

    if beat:
        os.environ['BRV_BEAT'] = 'True'
        os.system('celery beat -f logs/worker.log -l INFO --detach')
    else:
        os.environ['BRV_BEAT'] = 'False'

#-------------------------------------------------------------------------------
def main(argv):
    try:
        opts, args = getopt.getopt(argv,"cds", ['celerybeat', 'debug', 'sandbox'])
    except getopt.GetoptError:
        sys.exit(2)

    beat=None

    for opt, arg in opts:
        if opt in('-c', '--celerybeat'):
            beat = True
        elif opt in ('-d', '--debug'):
            app.config['DEBUG'] = True
        elif opt in ('-s', '--sandbox'):
            os.environ['BRV_SANDBOX'] = 'True'

    start_worker(beat=beat)
    sio_server.init_app(
        app,
        async_mode='eventlet',
        message_queue='amqp://')
    set_environ(app)
    startup_msg(app)

    sio_server.run(
        app,
        port=app.config['LOCAL_PORT'],
        log_output=False,
        use_reloader=False
    )

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
