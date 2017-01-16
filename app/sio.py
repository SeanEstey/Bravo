
import logging
from .utils import print_vars
from datetime import datetime
from flask import g, request, current_app
from flask_login import current_user
import flask_socketio
from . import sio_app
log = logging.getLogger(__name__)

@sio_app.on_error()
def _on_error(e):
    log.debug('socketio error=%s', str(e))

#-------------------------------------------------------------------------------
def broadcast(data):
    a = 1
    #log.debug('attempting sio_app broadcast')
    #dump()
    #_broadcast(data)

#-------------------------------------------------------------------------------
@sio_app.on('event')
def _broadcast(data):
    #log.debug('broadcasting to all clients')
    #sio_app.emit('analyze_routes', {})
    a = 1

#-------------------------------------------------------------------------------
@sio_app.on('connect')
def sio_connect():
    user_id = current_user.user_id

    if current_user.is_authenticated:
        if user_id not in current_app.clients.keys():
            current_app.clients[user_id] = request.namespace

    log.debug('<%s> connected', current_user.user_id) #, request.namespace)
    #log.debug('app.clients=%s', current_app.clients)

    #import pdb; pdb.set_trace()
    #dump()

#-------------------------------------------------------------------------------
@sio_app.on('disconnect')
def sio_disconnect():
    user_id = current_user.user_id

    if current_user.is_authenticated:
        current_app.clients.pop(user_id, None)

    log.debug('<%s> disconnected', current_user.user_id)

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
