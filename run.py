from app import app, socketio, info_handler, error_handler
#from tasks import celery_app

# Register all view functions with Flask application
#import views

import os
import time
import sys

import sys, getopt


def restart_celery_worker():
    os.system('kill %1')

    # Kill celery nodes with matching queue name. Leave others alone
    os.system("ps aux | grep 'queues " + app.config['DB'] + \
              "' | awk '{print $2}' | xargs kill -9")

    # Create workers
    os.system('celery worker -A app.celery_app -B -n ' + \
              app.config['DB'] + ' --queues ' + app.config['DB'] + ' &')

    # Pause to give workers time to initialize before starting server
    time.sleep(3)
    
    #if not celery_app.control.inspect().registered_tasks():
    #    app.logger.info('Celery process failed to start!')
    #else:
    #    app.logger.info('Server starting using \'%s\' DB', app.config['DB'])
    

def main(argv):
   try:
      opts, args = getopt.getopt(argv,"r:")
   except getopt.GetoptError:
      sys.exit(2)
   for opt, arg in opts:
      if opt == '-r':
            if arg == 'celery':
                print 'restarting celery worker'
                restart_celery_worker()
  
    if app.config['DEBUG'] == True:
        # Werkzeug server (Test Mode)
        app.run(port=app.config['LOCAL_PORT'], debug=True, threaded=True)
        #socketio.run(app, port=app.config['LOCAL_PORT'], threaded=THREADED)
    else:
        # Start eventlet server w/ socket.io enabled
        socketio.run(app, port=app.config['LOCAL_PORT'])

if __name__ == "__main__":
    main(sys.argv[1:])
    

