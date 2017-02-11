'''detect'''
import logging, os, requests, socket, time
import psutil
from logging import INFO
from os import environ as env
from app.tasks import celery as celery_app
import celery, eventlet, flask, flask_socketio
from app.logger import file_handler

SSL_CERT_PATH = '/etc/nginx/gd_bundle-g2-g1.crt'
G = '\033[92m'
Y = '\033[93m'
ENDC = '\033[0m'

log = logging.getLogger(__name__)
log_f = G + '%(message)s'
hdler = file_handler(INFO, 'info.log', log_f=log_f, log_v='')
log.addHandler(hdler)
log.setLevel(INFO)

#-------------------------------------------------------------------------------
def startup_msg(app):

    app.logger.info('server starting...\n')

    hostname = env['BRV_HOSTNAME']
    host = 'http://%s' %(env['BRV_IP'])
    debug = 'enabled' if app.config['DEBUG'] else 'disabled'
    sbox = 'enabled' if env['BRV_SANDBOX'] == 'True' else 'disabled'
    ssl = 'enabled (nginx)' if env['BRV_SSL'] == 'True' else 'disabled'
    evntlt_v = eventlet.__version__
    flsk_v = flask.__version__
    mem = psutil.virtual_memory()
    active = (mem.active/1000000)
    total = (mem.total/1000000)
    free = mem.free/1000000

    if free < 250:
        app.logger.info(\
            '%ssystem has less than 250mb free mem (%smb). '\
            'not recommended!\n', Y, free)

    bravo_msg =\
    "%s-------------------------------- %s%s\n"                       %(G,Y,os_desc()) +\
    "%s-  ____ ------------------------ %smem free: %s/%s\n"          %(G,G,free,total) +\
    "%s- |  _ \ ----------------------- %sbravo@%s%s\n"               %(G,Y,hostname,G) +\
    "%s- | |_) |_ __ __ ___   _____ --- %s%s\n"                       %(G,G,host) +\
    "%s- |  _ <| '__/ _` \ \ / / _ \ -- %s[config]\n"                 %(G,G) +\
    "%s- | |_) | | | (_| |\ V / (_) | - %s  > debug:   %s\n"          %(G,G,debug) +\
    "%s- |____/|_|  \__,_| \_/ \___/  - %s  > sandbox: %s\n"          %(G,G,sbox) +\
    "%s-------------------------------- %s  > running: flask %s\n"    %(G,G,flsk_v) +\
    "%s-------------------------------- %s  > server:  eventlet %s\n" %(G,G,evntlt_v) +\
    "%s-------------------------------- %s  > ssl:     %s"            %(G,G,ssl) +\
    ""

    log.info(bravo_msg)
    insp = celery_app.control.inspect()

    while not insp.ping():
        print 'waiting on celery worker...'
        time.sleep(1)
        insp = celery_app.control.inspect()

    stats = insp.stats()
    stats = stats[stats.keys()[0]]
    broker = stats['broker']
    trnsprt = broker['transport']

    n_workers = '%s' %(stats['pool']['max-concurrency'])
    str_brkr = '%s://%s:%s' %(trnsprt, broker['hostname'], broker['port'])
    beat = 'on' if env['BRV_BEAT'] == 'True' else 'off'
    clry_v = celery.__version__
    c_host = 'celery@bravo'
    regist = '%s regist.' % len(insp.registered()[c_host])
    sched = '%s sched.' % len(insp.scheduled()[c_host])

    log.info(\
    "%s-------------------------------- %scelery@bravo\n"      %(G,Y) +\
    "%s-------------------------------- %s%s\n"                %(G,G,str_brkr) +\
    "%s-------------------------------- %s[config]\n"          %(G,G) +\
    "%s-------------------------------- %s  > version: %s\n"   %(G,G,clry_v) +\
    "%s-------------------------------- %s  > workers: [%s]\n" %(G,G,n_workers) +\
    "%s-------------------------------- %s  > beat:    %s\n"   %(G,G,beat) +\
    "%s-------------------------------- %s  > tasks:   %s\n"   %(G,G,regist) +\
    "%s-------------------------------- %s  > tasks:   %s\n"   %(G,G,sched) +\
    "")

    print bravo_msg + ENDC
    app.logger.info('server ready!')

#-------------------------------------------------------------------------------
def set_environ(app):

    if not env.get('BRV_SANDBOX'):
        env['BRV_SANDBOX'] = 'False'

    env['BRV_HOSTNAME'] = hostname = socket.gethostname()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("gmail.com",80))
    env['BRV_IP'] = ip = s.getsockname()[0]
    env['BRV_DOMAIN'] = domain = socket.gethostbyaddr(ip)[0]
    s.close

    try:
        r = requests.get('https://%s' % domain, verify=SSL_CERT_PATH)
    except Exception as e:
        app.logger.debug('exception. SSL not enabled')
        env['BRV_SSL'] = 'False'
        env['BRV_HTTP_HOST'] = 'http://' + ip
    else:
        env['BRV_SSL'] = 'True'
        env['BRV_HTTP_HOST'] = 'https://' + ip

    try:
        domain = socket.gethostbyaddr(ip)
    except Exception as e:
        app.logger.debug('no domain found')
        env['BRV_TEST'] = 'True'
        return

    if domain[0] == 'bravoweb.ca':
        app.logger.debug('bravoweb.ca domain. deploy server')
        env['BRV_TEST'] = 'False'
    else:
        env['BRV_TEST'] = 'True'

#-------------------------------------------------------------------------------
def os_desc():
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
