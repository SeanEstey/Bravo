'''detect'''
import logging, os, time
import psutil
from logging import INFO
from os import environ
from app.tasks import celery as celery_app
import celery, eventlet, flask, flask_socketio
from app.utils import bcolors as c
from app.logger import file_handler
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def log_startup_info(sio_server, app):

    app.logger.info('server starting...\n')

    log_f = c.OKGREEN + '%(message)s' #+ c.ENDC
    hdler = file_handler(INFO, 'info.log', log_f=log_f, log_v='')
    log.addHandler(hdler)
    log.setLevel(INFO)

    hostname = environ['BRAVO_HOSTNAME']
    protocol = 'http://' #s://' if environ['BRAVO_SSL'] == 'True' else 'http://'
    host = '%s%s' %(protocol, environ['BRAVO_IP'])
    debug = 'enabled' if app.config['DEBUG'] else 'disabled'
    sandbox = 'enabled' if environ['BRAVO_SANDBOX_MODE'] == 'True' else 'disabled'
    ssl = 'enabled (nginx)' if environ['BRAVO_SSL'] == 'True' else 'disabled'


    mem = psutil.virtual_memory()
    active = (mem.active/1000000)
    total = (mem.total/1000000)
    free = mem.free/1000000

    if free < 250:
        app.logger.info(\
            '%ssystem has less than 250mb free mem (%smb). '\
            'not recommended!\n', c.WARNING, free)

    log.info(\
    "%s-------------------------------- %s%s\n"                         %(c.OKGREEN, c.WARNING, get_os_full_desc()) +\
    "%s-  ____ ------------------------ %smem free: %s/%s\n"            %(c.OKGREEN, c.OKGREEN, free, total) +\
    "%s- |  _ \ ----------------------- %s%sbravo@%s%s\n"               %(c.OKGREEN, c.WARNING, c.BOLD, hostname, c.OKGREEN) +\
    "%s- | |_) |_ __ __ ___   _____ --- %s%s\n"                         %(c.OKGREEN, c.OKGREEN, host) +\
    "%s- |  _ <| '__/ _` \ \ / / _ \ -- %s[config]\n"                   %(c.OKGREEN, c.OKGREEN) +\
    "%s- | |_) | | | (_| |\ V / (_) | - %s  > debug:   %s\n"          %(c.OKGREEN, c.OKGREEN, debug) +\
    "%s- |____/|_|  \__,_| \_/ \___/  - %s  > sandbox: %s\n"          %(c.OKGREEN, c.OKGREEN, sandbox) +\
    "%s-------------------------------- %s  > running: flask %s\n"    %(c.OKGREEN, c.OKGREEN, flask.__version__) +\
    "%s-------------------------------- %s  > server:  eventlet %s\n" %(c.OKGREEN, c.OKGREEN, eventlet.__version__) +\
    "%s-------------------------------- %s  > ssl:     %s"            %(c.OKGREEN, c.OKGREEN, ssl) +\
    "")

    inspect = celery_app.control.inspect()

    while not inspect.ping():
        app.logger.debug('waiting on celery worker...')
        time.sleep(1)
        inspect = celery_app.control.inspect()

    tasks_reg = '%s regist.' % len(inspect.registered().get('celery@bravo'))
    tasks_sch = '%s sched.' % len(inspect.scheduled().get('celery@bravo'))
    stats = inspect.stats()
    celery_host = stats.keys()[0]
    transport = stats[celery_host]['broker']['transport']
    worker = '%s' %(stats[celery_host]['pool']['max-concurrency'])
    broker_location = '%s://%s:%s' %(
        transport, stats[celery_host]['broker']['hostname'],
        stats[celery_host]['broker']['port'])
    beat = 'on' if environ['BRAVO_CELERY_BEAT'] == 'True' else 'off'

    log.info(\
    "%s-------------------------------- %scelery@bravo\n"      %(c.OKGREEN, c.WARNING) +\
    "%s-------------------------------- %s%s\n"                %(c.OKGREEN, c.OKGREEN, broker_location) +\
    "%s-------------------------------- %s[config]\n"          %(c.OKGREEN, c.OKGREEN) +\
    "%s-------------------------------- %s  > version: %s\n"   %(c.OKGREEN, c.OKGREEN, celery.__version__) +\
    "%s-------------------------------- %s  > workers: [%s]\n" %(c.OKGREEN, c.OKGREEN, worker) +\
    "%s-------------------------------- %s  > beat:    %s\n"   %(c.OKGREEN, c.OKGREEN, beat) +\
    "%s-------------------------------- %s  > tasks:   %s\n"   %(c.OKGREEN, c.OKGREEN, tasks_reg) +\
    "%s-------------------------------- %s  > tasks:   %s\n"     %(c.OKGREEN, c.OKGREEN, tasks_sch) +\
    "")

    app.logger.info('server ready!')

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
