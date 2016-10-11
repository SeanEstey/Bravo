import os
import time
import sys
import getopt
from flask_socketio import SocketIO

import config
from app import create_app, create_celery_app
#from app import celery

#flask_app = create_app('app')
from app.tasks import flask_app
socketio_app = SocketIO(flask_app)

#celery = create_celery_app(flask_app)

#celery.conf.update(flask_app.config)



def start_worker():
    # Create worker w/ embedded beat. Does not work
    # if more than 1 worker
    os.system('celery worker -A app.tasks.celery -B -n ' + \
              config.DB + ' --queues ' + config.DB + ' &')
    # Pause to give workers time to initialize before starting server
    time.sleep(2)

def restart_worker():
    os.system('kill %1')
    # Kill celery nodes with matching queue name. Leave others alone
    os.system("ps aux | grep 'queues " + config.DB + \
              "' | awk '{print $2}' | xargs kill -9")
    start_worker()


def main(argv):
    try:
        opts, args = getopt.getopt(argv,"c:m:")
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-c':
            if arg == 'restart':
                print 'restarting celery worker'
                restart_worker()
            elif arg == 'start':
                print 'starting celery worker'
                start_worker()
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

