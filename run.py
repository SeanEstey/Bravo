import os
import time
import sys
import getopt

from app import app, socketio

def start_celery_worker():
    # Create workers
    os.system('celery worker -A app.celery_app -B -n ' + \
              app.config['DB'] + ' --queues ' + app.config['DB'] + ' &')

    # Pause to give workers time to initialize before starting server
    time.sleep(3)
    
def restart_celery_worker():
    os.system('kill %1')

    # Kill celery nodes with matching queue name. Leave others alone
    os.system("ps aux | grep 'queues " + app.config['DB'] + \
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
        opts, args = getopt.getopt(argv,"c:")
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

    if app.config['DEBUG'] == True:
        # Werkzeug server (Test Mode)
        app.run(port=app.config['LOCAL_PORT'], debug=True, threaded=True)
        #socketio.run(app, port=app.config['LOCAL_PORT'], threaded=THREADED)
    else:
        # Start eventlet server w/ socket.io enabled
        socketio.run(app, port=app.config['LOCAL_PORT'])

if __name__ == "__main__":
    main(sys.argv[1:])
    

