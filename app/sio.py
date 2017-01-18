
import logging
from .utils import print_vars
from datetime import datetime
from flask import g, request, current_app
from flask_login import current_user
from flask_socketio import join_room, leave_room, send, emit
from . import sio_app
log = logging.getLogger(__name__)

@sio_app.on_error()
def _on_error(e):
    print 'socketio error=%s' % str(e)

#-------------------------------------------------------------------------------
@sio_app.on('join')
def on_join(data):
    user_id = current_user.user_id
    room = current_user.get_agency()
    join_room(room)
    log.debug('user_id=%s joining room=%s', user_id, room)
    send(user_id + ' has entered the room', room=room)
    emit('room_msg', 'for %s' % room, room=room)

#-------------------------------------------------------------------------------
def broadcast(data):
    #log.debug('attempting sio_app broadcast')
    #dump()
    #_broadcast(data)
    pass

#-------------------------------------------------------------------------------
@sio_app.on('event')
def _broadcast(data):
    #log.debug('broadcasting to all clients')
    #sio_app.emit('analyze_routes', {})
    pass

#-------------------------------------------------------------------------------
@sio_app.on('connect')
def sio_connect():
    #print 'current_user=%s' % current_user
    user_id = current_user.user_id

    if current_user.is_authenticated:
        if user_id not in current_app.clients.keys():
            current_app.clients[user_id] = request.namespace

    print '<%s> connected' % current_user.user_id
    #log.debug('app.clients=%s', current_app.clients)

    #import pdb; pdb.set_trace()
    #dump()

#-------------------------------------------------------------------------------
@sio_app.on('disconnect')
def sio_disconnect():
    user_id = current_user.user_id

    if current_user.is_authenticated:
        user_id = current_user.user_id
        room = current_user.get_agency()
        leave_room(room)
        print '%s leaving room=%s'%(user_id,room)
        current_app.clients.pop(user_id, None)
        print '<%s> disconnected, clients=%s' % (current_user.user_id, current_app.clients)

#-------------------------------------------------------------------------------
@sio_app.on('message')
def handle_msg(message):
    log.debug('rec msg=%s', message)

#-------------------------------------------------------------------------------
@sio_app.on('json')
def handle_json(json):
    log.debug('rec json=%s', json)

#-------------------------------------------------------------------------------
def dump():
    log.debug('sio_app: \n%s', print_vars(sio_app))
    log.debug('sio_app dir:\n%s', dir(sio_app))
    log.debug('sio_app.server: \n%s', print_vars(sio_app.server))
    log.debug('sio_app.server dir:\n%s', dir(sio_app.server))
    log.debug('request:\n%s', print_vars(request))
