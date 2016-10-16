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
from app import create_app, set_test_mode
from app.tasks import flask_app

socketio_app = SocketIO(flask_app)

import app.socketio

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
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("gmail.com",80))
    ip = s.getsockname()[0]
    s.close
    return ip

#-------------------------------------------------------------------------------
def start_worker():
    # Create worker w/ embedded beat. Does not work
    # if more than 1 worker
    os.system('celery worker -A app.tasks.celery -B -n ' + \
              config.DB + ' --queues ' + config.DB + ' &')
    # Pause to give workers time to initialize before starting server
    time.sleep(2)

#-------------------------------------------------------------------------------
def restart_worker():
    os.system('kill %1')
    # Kill celery nodes with matching queue name. Leave others alone
    os.system("ps aux | grep 'queues " + config.DB + \
              "' | awk '{print $2}' | xargs kill -9")
    start_worker()

#-------------------------------------------------------------------------------
def test_mode():
    set_test_mode()
    os.environ['BRAVO_TEST_MODE'] = 'True'

#-------------------------------------------------------------------------------
def main(argv):

    os.environ['BRAVO_TEST_MODE'] = 'False' # default
    os.environ['BRAVO_HTTP_HOST'] = 'http://' + get_local_ip()

    bravo_conf = [
        "FLASK: " + flask.__version__,
        "NGINX_HOST: http://%s:%s" % (
            os.environ['BRAVO_HTTP_HOST'],
            flask_app.config['PUB_PORT'])
    ]

    if socketio_app.server.async_mode == 'eventlet':
        bravo_conf += ['SERVER_SOFTWARE: EVENTLET (%s)' % eventlet.__version__]
    else:
        bravo_conf += ['SERVER_SOFTWARE: %s' % socketio_app.server.async_mode]

    try:
        opts, args = getopt.getopt(argv,"c:dt", ['celery=', 'debug', 'testmode'])
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in('-c', '--celery'):
            bravo_conf += ['CELERY: ENABLED (' + celery.__version__ +')' ]
            if arg == 'restart':
                restart_worker()
            elif arg == 'start':
                start_worker()
                celery_cmd = arg
        elif opt in ('-d', '--debug'):
            bravo_conf.append('DEBUG MODE: ENABLED')
            flask_app.config['DEBUG'] = True
        elif opt in ('-t', '--testmode'):
            test_mode()
            bravo_conf += ['TEST MODE: ENABLED']

    print bcolors.HEADER + '\n--------------------------------------' + bcolors.ENDC
    print bcolors.BOLD + 'Bravo' + bcolors.ENDC
    print json.dumps(bravo_conf, indent=0)[1:-2].replace('"', '')
    print bcolors.HEADER + '--------------------------------------\n' + bcolors.ENDC

    socketio_app.run(
        flask_app,
        port=flask_app.config['LOCAL_PORT']
        #use_reloader=True
    )

#-------------------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
