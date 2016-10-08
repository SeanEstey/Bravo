       wst = threading.Thread(target=self.serve_app, args=(sio,app))
        wst.daemon = True
        wst.start()

def serve_app(self, _sio, _app):
    app = socketio.Middleware(_sio, _app)
    eventlet.wsgi.server(eventlet.listen(('', 7000)), app)
