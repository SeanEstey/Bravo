'''app.socketio'''
import logging
from .utils import print_vars, inspector
from datetime import datetime
from flask import g, request, current_app, has_request_context
from flask_login import current_user
from flask_socketio import SocketIO, join_room, leave_room, send, emit, rooms
log = logging.getLogger(__name__)

# Main server initialized with flask app in run.py
sio_server = SocketIO()

# Client that uses message_queue to send emit signals to
# server. Can be used by celery tasks.
sio_client = SocketIO(message_queue='amqp://')

#-------------------------------------------------------------------------------
def smart_emit(event, data, room=None):
    '''Sends a socketio emit signal to the appropriate client (room).
    Can be called from celery task if part of a request (will be cancelled
    otherwise).
    '''
    #log.debug('smart_emit data=%s', data)

    if room:
        print 'smart_emit: sending to requested room=%s, event=%s' %(room,event)
        sio_client.emit(event, data, room=room)
    else:
        if current_user and current_user.is_authenticated:
            print 'smart_emit: sending to discovered room=%s'% current_user.agency
            sio_client.emit(event, data, room=current_user.agency)
        else:
            if not has_request_context():
                print 'smart_emit: no listeners, saving energy'
            else:
                print 'smart_emit: broadcasting to all clients'
                sio_client.emit(event, data)

#-------------------------------------------------------------------------------
@sio_server.on_error()
def _on_error(e):
    log.error('socketio error=%s', str(e))
    #print 'socketio error=%s' % str(e)

#-------------------------------------------------------------------------------
@sio_server.on('connect')
def sio_connect():
    '''Called before app.before_request'''
    smart_emit('test', 'smart_emit: connected!')

    if current_user.is_authenticated:
        user_id = current_user.user_id
        room = current_user.agency

        if room not in rooms():
            join_room(room)
            #log.debug('%s connected. room=%s', user_id, room)
            emit('joined', 'connected to room=%s' % room, room=room)
    else:
        print '<%s> connected' % current_user.user_id

#-------------------------------------------------------------------------------
@sio_server.on('disconnect')
def sio_disconnect():
    user_id = current_user.user_id

    if current_user.is_authenticated:
        user_id = current_user.user_id
        room = current_user.agency
        leave_room(room)
        print '%s leaving room=%s'%(user_id,room)
        print '<%s> disconnected' % (current_user.user_id)

#-------------------------------------------------------------------------------
@sio_server.on('analyze_routes')
def do_analyze_routes():
    log.debug('received analyze_routes req')
    from app.routing.tasks import discover_routes
    try:
        discover_routes.delay(agcy=current_user.agency)
    except Exception as e:
        log.debug('', exc_info=True)

#-------------------------------------------------------------------------------
def dump():
    log.debug('sio_server: \n%s', print_vars(sio_server))
    log.debug('sio_server dir:\n%s', dir(sio_server))
    log.debug('sio_server.server: \n%s', print_vars(sio_server.server))
    log.debug('sio_server.server dir:\n%s', dir(sio_server.server))
    log.debug('request:\n%s', print_vars(request))
