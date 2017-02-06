'''run'''
import logging, os, time, sys, getopt
from flask import current_app, g, session
from flask_login import current_user
from setup import startup_msg
from app import db_client, create_app, config_test_server, is_test_server
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
def start_worker(celery_beat):

    # Kill any existing worker/beat processes, start new worker

    os.system('kill %1')
    os.system("ps aux | grep '/usr/local/bin/celery beat' | awk '{print $2}' | xargs kill -9")
    os.system("ps aux | grep '/usr/local/bin/celery worker' | awk '{print $2}' | xargs kill -9")
    os.system('celery worker -A app.tasks.celery -n %s &' % app.config['DB'])

    # Start celery beat if option given

    if celery_beat:
        os.environ['BRAVO_CELERY_BEAT'] = 'True'
        os.system('celery beat &')
    else:
        os.environ['BRAVO_CELERY_BEAT'] = 'False'

#-------------------------------------------------------------------------------
def main(argv):
    try:
        opts, args = getopt.getopt(argv,"cds", ['celerybeat', 'debug', 'sandbox'])
    except getopt.GetoptError:
        sys.exit(2)

    sandbox = None
    celery_beat = None
    debug = None

    for opt, arg in opts:
        if opt in('-c', '--celerybeat'):
            celery_beat = True
        elif opt in ('-d', '--debug'):
            app.config['DEBUG'] = True
        elif opt in ('-s', '--sandbox'):
            sandbox = True

    if not app.config['DEBUG']:
        app.config['DEBUG'] = False

    if is_test_server():
        if sandbox == True:
            config_test_server('sandbox')
        else:
            config_test_server('test_server')
    else:
        os.environ['BRAVO_SANDBOX_MODE'] = 'False'

    sio_server.init_app(app, async_mode='eventlet', message_queue='amqp://')

    start_worker(celery_beat)

    app.logger.info('server restarted')
    msg = startup_msg(sio_server, app)
    for ln in msg:
        app.logger.info(ln)

    sio_server.run(
        app,
        port=app.config['LOCAL_PORT'],
        use_reloader=True)

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
