'''detect'''
import os
from os import environ
import eventlet
import celery
import flask
import flask_socketio
import socket

#-------------------------------------------------------------------------------
def startup_msg(sio_server, app):

    protocol = 'https://' if environ['BRAVO_SSL'] == 'True' else 'http://'
    host = '%s%s' %(protocol, environ['BRAVO_IP'])

    from app.tasks import celery as celery_app

    inspect = celery_app.control.inspect()
    tasks = '%s registered, %s scheduled' %(
        len(inspect.registered().get('celery@bravo')),
        len(inspect.scheduled().get('celery@bravo')))
    stats = inspect.stats()
    celery_host = stats.keys()[0]
    transport = stats[celery_host]['broker']['transport']

    worker = '%s' %(
        stats[celery_host]['pool']['max-concurrency'])
    broker_location = '%s://%s:%s' %(
        transport, stats[celery_host]['broker']['hostname'],
        stats[celery_host]['broker']['port'])

    debug = 'enabled' if app.config['DEBUG'] else 'disabled'
    sandbox = 'enabled' if environ['BRAVO_SANDBOX_MODE'] == 'True' else 'disabled'
    beat = 'on' if environ['BRAVO_CELERY_BEAT'] == 'True' else 'off'

    msg = []
    #msg.append('--------------------------------------------------')
    msg.append('bravo@%s' % os.environ['BRAVO_HOSTNAME'])
    msg.append('%s' % host)
    msg.append('-> debug:     %s' % debug)
    msg.append('-> sandbox:   %s' % sandbox)
    msg.append('-> scheduler: %s' % beat)
    msg.append('-> server:    [Flask %s, Eventlet %s]' %(
        flask.__version__, eventlet.__version__))
    msg.append('-> software:  [Flask_SocketIO %s, Celery %s]' %(
        flask_socketio.__version__, celery.__version__))
    msg.append('-> system:    %s' % get_os_full_desc())
    msg.append('celery@bravo')
    msg.append(broker_location)
    msg.append('-> workers:   %s' % worker)
    msg.append('-> tasks:     %s' % tasks)
    #msg.append('--------------------------------------------------\n')

    return msg

#-------------------------------------------------------------------------------
def get_os_full_desc():
    from os.path import isfile
    name = ''
    if isfile('/etc/lsb-release'):
        lines = open('/etc/lsb-release').read().split('\n')
        for line in lines:
            if line.startswith('DISTRIB_DESCRIPTION='):
                name = line.split('=')[1]
                if name[0]=='"' and name[-1]=='"':
                    return name[1:-1]
    if isfile('/suse/etc/SuSE-release'):
        return open('/suse/etc/SuSE-release').read().split('\n')[0]
    try:
        import platform
        return ' '.join(platform.dist()).strip().title()
        #return platform.platform().replace('-', ' ')
    except ImportError:
        pass
    if os.name=='posix':
        osType = os.getenv('OSTYPE')
        if osType!='':
            return osType
    ## sys.platform == 'linux2'
    return os.name
