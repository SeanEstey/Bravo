'''app.socketio'''

from flask import request, jsonify
from flask_socketio import SocketIO, send, emit
import logging

from tasks import flask_app
logger = logging.getLogger(__name__)

socketio_app = SocketIO(flask_app)

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


