import os
import time
import sys
import getopt
from flask_socketio import SocketIO

import config
from app import create_app, create_celery_app

flask_app = create_app()
celery_app = create_celery_app(flask_app)
socketio_app = SocketIO(flask_app)


def create_log_dir():
    os.system('mkdir /var/www/bravo')
    os.system('mkdir /var/www/bravo/logs')

def start_celery_worker():
    # Create workers
    os.system('celery worker -A run.celery_app -B -n ' + \
              config.DB + ' --queues ' + config.DB + ' &')

    # Pause to give workers time to initialize before starting server
    time.sleep(3)

def restart_celery_worker():
    os.system('kill %1')

    # Kill celery nodes with matching queue name. Leave others alone
    os.system("ps aux | grep 'queues " + config.DB + \
              "' | awk '{print $2}' | xargs kill -9")

    start_celery_worker()

def main(argv):
    '''
    Start celery worker:
        python run.py -c start
    Restart celery worker:
        python run.py -c restart
    '''

    try:
        opts, args = getopt.getopt(argv,"c:m:")
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-c':
            if arg == 'restart':
                print 'restarting celery worker'
                restart_celery_worker()
            elif arg == 'start':
                print 'starting celery worker'
                start_celery_worker()
        elif opt == '-m':
            if arg == 'debug':
                flask_app.config['DEBUG'] = True
            elif arg == 'release':
                flask_app.config['DEBUG'] = False


    if flask_app.config['DEBUG'] == True:
        # Werkzeug server (Test Mode)
        flask_app.run(port=flask_app.config['LOCAL_PORT'], debug=True, threaded=True)
        #socketio.run(app, port=app.config['LOCAL_PORT'], threaded=THREADED)
    else:
        # Start eventlet server w/ socket.io enabled
        socketio.run(flask_app, port=flask_app.config['LOCAL_PORT'])

if __name__ == "__main__":
    main(sys.argv[1:])

