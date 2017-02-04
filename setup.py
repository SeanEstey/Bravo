import os
import eventlet
import celery
import flask
import flask_socketio
from app.utils import bcolors

#-------------------------------------------------------------------------------
def startup_msg(sio_server, app):
    msg = []
    msg.append( '--------------------------------------')
    msg.append( 'Bravo')

    if os.environ['BRAVO_TEST_SERVER'] == 'True':
        msg.append( 'HOSTNAME: Test Server')
    else:
        msg.append( 'HOSTNAME: Deploy Server')

    msg.append( "HTTP_HOST: %s:%s" %(os.environ['BRAVO_HTTP_HOST'],app.config['PUB_PORT']))

    if app.config['DEBUG'] == True:
        msg.append( 'DEBUG MODE: ENABLED')
    else:
        msg.append( 'DEBUG MODE: DISABLED')
    if os.environ['BRAVO_SANDBOX_MODE'] == 'True':
        msg.append( 'SANDBOX MODE: ENABLED (blocking all outgoing Voice/Sms/Email messages)')
    else:
        msg.append( 'SANDBOX MODE: DISABLED')
    if os.environ['BRAVO_CELERY_BEAT'] == 'True':
        msg.append( 'CELERY_BEAT: ENABLED')
    elif os.environ['BRAVO_CELERY_BEAT'] == 'False':
        msg.append( 'CELERY_BEAT: DISABLED (no automatic task scheduling)')

    msg.append( 'FLASK_SOCKETIO: %s' % flask_socketio.__version__)

    if sio_server.server.async_mode == 'eventlet':
        msg.append( 'SERVER_SOFTWARE: Eventlet (%s)' % eventlet.__version__)
    else:
        msg.append( 'SERVER_SOFTWARE: %s' % sio_server.server.async_mode)
    msg.append( 'CELERY: %s' % celery.__version__)
    msg.append( 'FLASK: %s' % flask.__version__)
    msg.append( '--------------------------------------')
    return msg

#-------------------------------------------------------------------------------
def copy_files():
    # PHP
    os.system('mkdir /var/www')
    os.system('mkdir /var/www/bravo')
    os.system('mkdir /var/www/bravo/logs')
    os.system('mkdir /var/www/bravo/php')
    os.system('mkdir /var/www/bravo/php/lib')
    os.system('cp -avr php /var/www/bravo/')

    os.system('chown -R www-data:www-data /var/www/bravo/logs')
    #os.system('chmod +x

    os.system('cp virtual_host/default /etc/nginx/sites-enabled/')
    os.system('service nginx restart')

    os.system('cp logrotate/bravo /etc/logrotate.d/')
    os.system('logrotate --force /etc/logrotate.d/bravo')

if __name__ == "__main__":
    copy_files()
