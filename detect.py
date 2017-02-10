'''detect'''
import logging, os, time
import psutil
from logging import INFO
from os import environ
import celery, eventlet, flask, flask_socketio
from app.utils import bcolors as c
from app.logger import file_handler
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def log_startup_info(sio_server, app):

    app.logger.info('server starting...\n')

    t1 = c.OKBLUE +  ' _________________'
    t2 = c.OKBLUE +  '/*****************\\' + c.OKGREEN
    mp = c.OKBLUE +  '|*****************|' + c.OKGREEN
    bp = c.OKBLUE +  '\______Ready! ____/' + c.OKGREEN

    log_f = c.OKGREEN + '%(message)s' #+ c.ENDC
    hdler = file_handler(INFO, 'info.log', log_f=log_f, log_v='')
    log.addHandler(hdler)
    log.setLevel(INFO)

    hostname = environ['BRAVO_HOSTNAME']
    protocol = 'https://' if environ['BRAVO_SSL'] == 'True' else 'http://'
    host = '%s%s' %(protocol, environ['BRAVO_IP'])
    debug = 'enabled' if app.config['DEBUG'] else 'disabled'
    sandbox = 'enabled' if environ['BRAVO_SANDBOX_MODE'] == 'True' else 'disabled'
    beat = 'on' if environ['BRAVO_CELERY_BEAT'] == 'True' else 'off'

    mem = psutil.virtual_memory()
    active = (mem.active/1000000)
    total = (mem.total/1000000)
    free = mem.free/1000000

    log.info(t1)
    log.info('%s %s%s', t2, c.WARNING, get_os_full_desc())
    log.info('%s mem free: %s/%s', mp, free, total)
    log.info('%s %s%sbravo@%s%s' %(mp, c.WARNING, c.BOLD, hostname, c.ENDC))
    log.info('%s %s' % (mp, host))
    log.info('%s [config]'% mp)
    log.info('%s -> debug:   %s' % (mp,debug))
    log.info('%s -> sandbox: %s' % (mp,sandbox))
    log.info('%s -> running: flask %s' % (mp, flask.__version__))
    log.info('%s -> server:  eventlet %s' % (mp, eventlet.__version__))

    from app.tasks import celery as celery_app
    inspect = celery_app.control.inspect()

    while not inspect.ping():
        app.logger.debug('waiting on celery worker...')
        time.sleep(1)
        inspect = celery_app.control.inspect()

    tasks_reg = '%s registered' % len(inspect.registered().get('celery@bravo'))
    tasks_sch = '%s scheduled' % len(inspect.scheduled().get('celery@bravo'))
    stats = inspect.stats()
    celery_host = stats.keys()[0]
    transport = stats[celery_host]['broker']['transport']
    worker = '%s' %(stats[celery_host]['pool']['max-concurrency'])
    broker_location = '%s://%s:%s' %(
        transport, stats[celery_host]['broker']['hostname'],
        stats[celery_host]['broker']['port'])

    log.info('%s %scelery@bravo%s' %(mp, c.WARNING, c.ENDC))
    log.info('%s %s' %(mp, broker_location))
    log.info('%s [config]' % mp)
    log.info('%s -> version: %s' % (mp, celery.__version__))
    log.info('%s -> workers: [%s]' % (mp, worker))
    log.info('%s -> beat:    %s' % (mp, beat))
    log.info('%s -> tasks:   %s' % (mp, tasks_reg))
    log.info('%s -> tasks:   %s\n' % (bp, tasks_sch))

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
