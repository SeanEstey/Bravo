'''run'''

import os
import time
import sys
import logging
import getopt
import flask
from flask import g, session
from flask_login import current_user
from setup import startup_msg
from app import sio_app, db_client, create_app, get_db, config_test_server, is_test_server
from app.utils import bcolors, print_vars
from app import sio

app = create_app('app')

#-------------------------------------------------------------------------------
@app.before_request
def do_setup():
    session.permanent = True
    g.db = db_client['bravo']
    g.user = current_user

    #app.logger.debug('app.before_req | setting g.db')
    print 'app.before_request g.db=True'

#-------------------------------------------------------------------------------
@app.after_request
def do_teardown(response):
    return response

#-------------------------------------------------------------------------------
def start_worker(celery_beat):
    db_name = app.config['DB']

    # Kill any existing workers
    os.system('kill %1')
    os.system("ps aux | grep 'queues " + db_name + \
              "' | awk '{print $2}' | xargs kill -9")

    if celery_beat:
        # Start worker with embedded beat (will fail if > 1 worker)
        os.environ['BRAVO_CELERY_BEAT'] = 'True'
        os.system('celery worker -A app.tasks.celery -B -n ' + \
                  db_name + ' --queues ' + db_name + ' &')
    else:
        # Start worker without beat
        os.environ['BRAVO_CELERY_BEAT'] = 'False'
        os.system('celery worker -A app.tasks.celery -n ' + \
                  db_name + ' --queues ' + db_name + ' &')

    # Pause to give workers time to initialize before starting server
    time.sleep(2)

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

    start_worker(celery_beat)

    sio_app.init_app(app, async_mode='eventlet', message_queue='amqp://')

    from app.tasks import mod_environ
    mod_environ.async(
        args=[{'BRAVO_SANDBOX_MODE':os.environ['BRAVO_SANDBOX_MODE'],
        'BRAVO_HTTP_HOST': os.environ['BRAVO_HTTP_HOST']}])

    startup_msg(sio_app, app)

    sio_app.run(
        app,
        port=app.config['LOCAL_PORT']
        #use_reloader=True
    )

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
