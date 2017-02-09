'''detect'''
import os
import eventlet
import celery
import flask
import flask_socketio
import socket

#-------------------------------------------------------------------------------
def startup_msg(sio_server, app):
    msg = []
    msg.append('--------------------------------------------------')
    if os.environ['BRAVO_SSL'] == 'True':
        host = 'https://%s' % os.environ['BRAVO_IP']
    else:
        host = 'http://%s' % os.environ['BRAVO_IP']
    msg.append('Bravo@%s' % os.environ['BRAVO_HOSTNAME'])
    msg.append('%s' % host)

    if app.config['DEBUG'] == True:
        msg.append('-> debug:     enabled')
    else:
        msg.append('-> debug:     disabled')
    if os.environ['BRAVO_SANDBOX_MODE'] == 'True':
        msg.append('--> sandbox:   enabled') # (blocking all outgoing Voice/Sms/Email messages)')
    else:
        msg.append('-> sandbox:   disabled')
    if os.environ['BRAVO_CELERY_BEAT'] == 'True':
        msg.append('-> scheduler: on')
    elif os.environ['BRAVO_CELERY_BEAT'] == 'False':
        msg.append('-> scheduler: off') # (no automatic task scheduling)')
    msg.append('-> server:    [flask %s, eventlet %s]' %(
        flask.__version__, eventlet.__version__))
    msg.append('-> software:  [flask_socketio %s, celery %s]' %(
        flask_socketio.__version__, celery.__version__))
    msg.append('-> system:    %s' % get_os_full_desc())
    msg.append('--------------------------------------------------\n')
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
