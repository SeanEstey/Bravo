'''app.main.socketio'''
from datetime import datetime
from flask import g, request, has_request_context
from flask_login import current_user
from flask_socketio import SocketIO, join_room, leave_room, send, emit, rooms
from app.lib.utils import obj_vars
from logging import getLogger
log = getLogger(__name__)

# Main server initialized with flask app in run.py
sio_server = SocketIO()

# Client that uses message_queue to send emit signals to
# server. Can be used by celery tasks.
sio_client = SocketIO(message_queue='amqp://')

import eventlet
eventlet.monkey_patch()

#-------------------------------------------------------------------------------
def smart_emit(event, data, room=None):
    '''Sends a socketio emit signal to the appropriate client (room).
    Can be called from celery task if part of a request (will be cancelled
    otherwise).
    '''

    if room:
        sio_client.emit(event, data, room=room)
    else:
        if current_user and current_user.is_authenticated:
            sio_client.emit(event, data, room=current_user.group)
        else:
            if not has_request_context():
                pass
            else:
                sio_client.emit(event, data)

#-------------------------------------------------------------------------------
@sio_server.on_error()
def _on_error(e):
    log.error('socketio error=%s', str(e))

#-------------------------------------------------------------------------------
@sio_server.on('connect')
def sio_connect():
    '''Called before app.before_request'''
    smart_emit('test', 'smart_emit: connected!')

    if current_user.is_authenticated:
        user_id = current_user.user_id
        room = current_user.group

        if room not in rooms():
            join_room(room)
            emit('joined', 'connected to room=%s' % room, room=room)
    else:
        pass

#-------------------------------------------------------------------------------
@sio_server.on('disconnect')
def sio_disconnect():
    user_id = current_user.user_id

    if current_user.is_authenticated:
        user_id = current_user.user_id
        room = current_user.group
        leave_room(room)

#-------------------------------------------------------------------------------
def dump():
    log.debug('sio_server: \n%s', obj_vars(sio_server))
    log.debug('sio_server dir:\n%s', dir(sio_server))
    log.debug('sio_server.server: \n%s', obj_vars(sio_server.server))
    log.debug('sio_server.server dir:\n%s', dir(sio_server.server))
    log.debug('request:\n%s', obj_vars(request))
