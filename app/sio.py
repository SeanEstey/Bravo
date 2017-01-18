
import logging
from .utils import print_vars
from datetime import datetime
from flask import g, request, current_app
from flask_login import current_user
from flask_socketio import join_room, leave_room, send, emit, rooms
from . import sio_app
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@sio_app.on_error()
def _on_error(e):
    log.error('socketio error=%s', str(e))
    #print 'socketio error=%s' % str(e)

#-------------------------------------------------------------------------------
@sio_app.on('connect')
def sio_connect():
    '''Called before app.before_request'''

    if current_user.is_authenticated:
        user_id = current_user.user_id
        room = current_user.agency

        if room not in rooms():
            join_room(room)
            log.debug('%s connected. room=%s', user_id)
            emit('joined', 'connected to room=%s' % room, room=room)
    else:
        print '<%s> connected' % current_user.user_id

#-------------------------------------------------------------------------------
@sio_app.on('disconnect')
def sio_disconnect():
    user_id = current_user.user_id

    if current_user.is_authenticated:
        user_id = current_user.user_id
        room = current_user.get_agency()
        leave_room(room)
        print '%s leaving room=%s'%(user_id,room)
        print '<%s> disconnected' % (current_user.user_id)

#-------------------------------------------------------------------------------
def dump():
    log.debug('sio_app: \n%s', print_vars(sio_app))
    log.debug('sio_app dir:\n%s', dir(sio_app))
    log.debug('sio_app.server: \n%s', print_vars(sio_app.server))
    log.debug('sio_app.server dir:\n%s', dir(sio_app.server))
    log.debug('request:\n%s', print_vars(request))
