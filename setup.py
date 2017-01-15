import os
import eventlet
import celery
import flask
from app.utils import bcolors

#-------------------------------------------------------------------------------
def startup_msg(sio_app, app):
    print bcolors.OKGREEN + '\n--------------------------------------'
    print bcolors.BOLD + 'Bravo' + bcolors.ENDC + bcolors.OKGREEN
    if os.environ['BRAVO_TEST_SERVER'] == 'True':
        print 'HOSTNAME: Test Server'
    else:
        print 'HOSTNAME: Deploy Server'
    print "HTTP_HOST: %s:%s" %(
        os.environ['BRAVO_HTTP_HOST'],
        app.config['PUB_PORT'])
    if app.config['DEBUG'] == True:
        print 'DEBUG MODE: ENABLED'
    else:
        print 'DEBUG MODE: DISABLED'
    if os.environ['BRAVO_SANDBOX_MODE'] == 'True':
        print 'SANDBOX MODE: ENABLED (blocking all outgoing Voice/Sms/Email messages) '
    else:
        print 'SANDBOX MODE: DISABLED'
    if os.environ['BRAVO_CELERY_BEAT'] == 'True':
        print 'CELERY_BEAT: ENABLED'
    elif os.environ['BRAVO_CELERY_BEAT'] == 'False':
        print 'CELERY_BEAT: DISABLED (no automatic task scheduling)'
    if sio_app.server.async_mode == 'eventlet':
        print 'SERVER_SOFTWARE: Eventlet (%s)' % eventlet.__version__
    else:
        print 'SERVER_SOFTWARE: %s' % sio_app.server.async_mode
    print 'CELERY: ' + celery.__version__
    print 'FLASK: ' + flask.__version__
    print '--------------------------------------\n' + bcolors.ENDC

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
