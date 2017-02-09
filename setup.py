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
    msg.append('--------------------------------------------------\n')
    return msg

if __name__ == "__main__":
    os.system('mkdir /var/www/bravo')
    os.system('mkdir /var/www/bravo/logs')
    os.system('chown -R www-data:root /var/www/bravo/logs')
    os.system('cp virtual_host/default /etc/nginx/sites-enabled/')
    os.system('service nginx restart')
    os.system('cp logrotate/bravo /etc/logrotate.d/')
    os.system('logrotate --force /etc/logrotate.d/bravo')
