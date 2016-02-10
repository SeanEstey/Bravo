import os
import time
import sys

import app
from app import flask_app, celery_app, db, logger, socketio
from private_config import *
from views import *

if __name__ == "__main__":
  os.system('kill %1')
  
  # Kill celery nodes with matching queue name. Leave others alone 
  os.system("ps aux | grep 'queues " + DB_NAME + "' | awk '{print $2}' | xargs kill -9")
  
  # Create workers
  #os.system('celery worker -A app.celery_app -f log -B -n ' + DB_NAME + ' --queues ' + DB_NAME + ' &')
  os.system('celery worker -A app.celery_app -B -n ' + DB_NAME + ' --queues ' + DB_NAME + ' &')
  
  # Pause to give workers time to initialize before starting server
  time.sleep(3);
  
  if not celery_app.control.inspect().registered_tasks():
    logger.info('Celery process failed to start!')
  else:
    logger.info('Server starting using \'%s\' DB', DB_NAME)

    # Start gevent server
    socketio.run(flask_app, port=LOCAL_PORT)
