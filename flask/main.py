import os
import time
import sys

from app import app, db, logger, socketio
from server_settings import *
from views import *
import tasks
from tasks import *

if __name__ == "__main__":
  os.system('kill %1')
  
  # Kill celery nodes with matching queue name. Leave others alone 
  os.system("ps aux | grep 'queues " + DB_NAME + "' | awk '{print $2}' | xargs kill -9")
  
  # Create workers
  os.system('celery worker -A tasks.celery_app -f log -B -n ' + DB_NAME + ' --queues ' + DB_NAME + ' &')
  
  # Pause to give workers time to initialize before starting server
  time.sleep(3);
  
  if not tasks.celery_app.control.inspect().registered_tasks():
    logger.info('Celery process failed to start!')
  else:
    logger.info('Server starting using \'%s\' DB', DB_NAME)

    # Start gevent server
    socketio.run(app, port=LOCAL_PORT)
