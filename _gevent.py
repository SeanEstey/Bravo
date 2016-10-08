import gevent
import gevent.monkey
gevent.monkey.patch_all()

import requests

from gevent.pywsgi import WSGIServer


# app = YourBottleApp

def alarm():
    '''
    Run this service every X duration
    '''
    ALARM = 21 
    while 1:
        #checking time and doing something. Then finding INTERVAL
        gevent.sleep(INTERVAL)


if __name__ == '__main__':
    http_server = WSGIServer(('', 8080), app)
    srv_greenlet = gevent.spawn(http_server.serve_forever)
    alarm_greenlet = gevent.spawn(alarm)

    try:
        gevent.joinall([srv_greenlet, alarm_greenlet])
    except KeyboardInterrupt:
        http_server.stop()
        print 'Quitting'
