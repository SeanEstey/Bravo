from app import flask_app, socketio, info_handler, error_handler
from tasks import celery_app
from config import *
from views import * # Register all view functions with Flask application

import os
import time
import sys

if __name__ == "__main__":
    os.system('kill %1')

    # Kill celery nodes with matching queue name. Leave others alone
    os.system("ps aux | grep 'queues " + DB_NAME + "' | awk '{print $2}' | xargs kill -9")

    # Create workers
    os.system('celery worker -A tasks.celery_app -B -n ' + DB_NAME + ' --queues ' + DB_NAME + ' &')

    # Pause to give workers time to initialize before starting server
    time.sleep(3)

    if not celery_app.control.inspect().registered_tasks():
        flask_app.logger.info('Celery process failed to start!')
    else:
        flask_app.logger.info('Server starting using \'%s\' DB', DB_NAME)

    if DEBUG == True:
        # Werkzeug server (Test Mode)
        flask_app.run(port=LOCAL_PORT, debug=True, threaded=True)
        #socketio.run(flask_app, port=LOCAL_PORT, threaded=THREADED)
    else:
        # Start eventlet server w/ socket.io enabled
        socketio.run(flask_app, port=LOCAL_PORT)
