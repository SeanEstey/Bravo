'''run'''

import os
import socket
import time
import pprint
import json
import sys
import getopt
import eventlet
import flask
import celery
from flask_socketio import SocketIO

import config
from app import config_test_server, is_test_server
from app.tasks import flask_app
from app.socketio import socketio_app
import app


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


#-------------------------------------------------------------------------------
def startup_msg():
    print bcolors.OKGREEN + '\n--------------------------------------'
    print bcolors.BOLD + 'Bravo' + bcolors.ENDC + bcolors.OKGREEN
    if os.environ['BRAVO_TEST_SERVER'] == 'True':
        print 'HOSTNAME: Test Server'
    else:
        print 'HOSTNAME: Deploy Server'
    print "HTTP_HOST: %s:%s" %(
        os.environ['BRAVO_HTTP_HOST'],
        flask_app.config['PUB_PORT'])
    if flask_app.config['DEBUG'] == True:
        print 'DEBUG MODE: ENABLED'
    else:
        print 'DEBUG MODE: DISABLED'
    if os.environ['BRAVO_SANDBOX_MODE'] == 'True':
        print 'SANDBOX MODE: ENABLED (blocking all outgoing Voice/Sms/Email messages) '
    else:
        print 'SANDBOX MODE: DISABLED'
    if os.environ['BRAVO_CELERY_BEAT'] == 'True':
        print 'CELERY_BEAT: ENABLED'
    elif os.environ['BRAVO_CELERY_BEAT'] == 'False':
        print 'CELERY_BEAT: DISABLED (no automatic task scheduling)'
    if socketio_app.server.async_mode == 'eventlet':
        print 'SERVER_SOFTWARE: Eventlet (%s)' % eventlet.__version__
    else:
        print 'SERVER_SOFTWARE: %s' % socketio_app.server.async_mode
    print 'CELERY: ' + celery.__version__
    print 'FLASK: ' + flask.__version__
    print '--------------------------------------\n' + bcolors.ENDC


#-------------------------------------------------------------------------------
def start_worker(celery_beat):
    # Kill any existing workers
    os.system('kill %1')
    os.system("ps aux | grep 'queues " + config.DB + \
              "' | awk '{print $2}' | xargs kill -9")

    if celery_beat:
        # Start worker with embedded beat (will fail if > 1 worker)
        os.environ['BRAVO_CELERY_BEAT'] = 'True'
        os.system('celery worker -A app.tasks.celery -B -n ' + \
                  config.DB + ' --queues ' + config.DB + ' &')
    else:
        # Start worker without beat
        os.environ['BRAVO_CELERY_BEAT'] = 'False'
        os.system('celery worker -A app.tasks.celery -n ' + \
                  config.DB + ' --queues ' + config.DB + ' &')

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
            flask_app.config['DEBUG'] = True
        elif opt in ('-s', '--sandbox'):
            sandbox = True


    if not flask_app.config['DEBUG']:
        flask_app.config['DEBUG'] = False

    if is_test_server():
        if sandbox == True:
            config_test_server('sandbox')
        else:
            config_test_server('test_server')
    else:
        os.environ['BRAVO_SANDBOX_MODE'] = 'False'

    start_worker(celery_beat)

    app.tasks.mod_environ.apply_async(
        args=[{'BRAVO_SANDBOX_MODE':os.environ['BRAVO_SANDBOX_MODE'],
        'BRAVO_HTTP_HOST': os.environ['BRAVO_HTTP_HOST']}],
        queue=flask_app.config['DB']
    )

    startup_msg()

    socketio_app.run(
        flask_app,
        port=flask_app.config['LOCAL_PORT']
        #use_reloader=True
    )

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
