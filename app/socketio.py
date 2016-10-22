'''app.socketio'''

from flask import request, jsonify
from flask_socketio import SocketIO, send, emit
import logging
import requests

from tasks import flask_app
logger = logging.getLogger(__name__)

socketio_app = SocketIO(flask_app)

#-------------------------------------------------------------------------------
def send_from_task(event, data):
    '''Used by celery worker to send SocketIO messages'''
    payload = {
        'event': event,
        'data':data
    }
    return requests.post('http://localhost/sendsocket', json=payload)

#-------------------------------------------------------------------------------
@socketio_app.on('disconnect')
def disconnected():
    print 'disconnect'
    return True

#-------------------------------------------------------------------------------
@socketio_app.on('connect')
def connected():
    #logger.info('socket.io connected')

    emit('connected')


