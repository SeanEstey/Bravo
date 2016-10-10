from flask_socketio import SocketIO

#-------------------------------------------------------------------------------
@socketio.on('disconnect')
def socketio_disconnected():
    return True
    #app.logger.debug('socket disconnected')

    #app.logger.debug(
    #'num connected sockets: ' +
    #str(len(socketio.server.sockets))
    #)

#-------------------------------------------------------------------------------
@socketio.on('connect')
def socketio_connect():
    return True
    #app.logger.debug('socket.io connected')

    #app.logger.debug(
    #    'num connected sockets: ' +
    #    str(len(socketio.server.sockets))
    #)
    #socketio.emit('msg', 'ping from server!');

    #emit('connected')
