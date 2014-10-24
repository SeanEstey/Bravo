from multiprocessing import Process

from flask import request

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
      raise RuntimeError('Not running with the Werkzeug Server')
      func()


shutdown_server()


def run_server():
    app.run()

    server = Process(target=app.run)
    server.start()
# ...
    server.terminate()
    server.join()
