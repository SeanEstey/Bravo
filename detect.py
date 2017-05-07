'''detect'''
import os, requests, socket, sys, time
from flask import current_app, g
import psutil
from os import environ as env
from app.tasks import celery as celery_app
import celery, eventlet, flask
from logging import getLogger
log = getLogger(__name__)

G = '\033[92m'
Y = '\033[93m'
ENDC = '\033[0m'

#-------------------------------------------------------------------------------
def startup_msg(app):

    hostname = env['BRV_HOSTNAME']
    host = 'http://%s' %(env['BRV_IP'])
    domain = env['BRV_DOMAIN'] if env['BRV_DOMAIN'] != 'False' else 'NO_DOMAIN'
    debug = 'enabled' if app.config['DEBUG'] else 'disabled'
    sbox = 'enabled' if env['BRV_SANDBOX'] == 'True' else 'disabled'
    ssl = 'enabled (nginx)' if env['BRV_SSL'] == 'True' else 'disabled'
    evntlt_v = eventlet.__version__
    flsk_v = flask.__version__

    from app.main.tasks import mem_check
    mem = mem_check()
    active = (mem.active/1000000)
    total = (mem.total/1000000)
    free = mem.free/1000000

    bravo_msg =\
    "%s-------------------------------- %s%s\n"                       %(G,Y,os_desc()) +\
    "%s-  ____ ------------------------ %smem free: %s/%s\n"          %(G,G,free,total) +\
    "%s- |  _ \ ----------------------- %s%s@%s%s\n"                  %(G,Y,hostname,domain,G) +\
    "%s- | |_) |_ __ __ ___   _____ --- %s%s\n"                       %(G,G,host) +\
    "%s- |  _ <| '__/ _` \ \ / / _ \ -- %s[config]\n"                 %(G,G) +\
    "%s- | |_) | | | (_| |\ V / (_) | - %s  > debug:   %s\n"          %(G,G,debug) +\
    "%s- |____/|_|  \__,_| \_/ \___/  - %s  > sandbox: %s\n"          %(G,G,sbox) +\
    "%s-------------------------------- %s  > running: flask %s, eventlet %s\n" %(G,G,flsk_v,evntlt_v) +\
    "%s-------------------------------- %s  > ssl:     %s"            %(G,G,ssl) +\
    ""

    insp = celery_app.control.inspect()
    while not insp.stats():
        time.sleep(1)

    stats = insp.stats()
    stats = stats[stats.keys()[0]]
    broker = stats['broker']
    trnsprt = broker['transport']

    n_workers = '%s' %(stats['pool']['max-concurrency'])
    str_brkr = '%s://%s:%s' %(trnsprt, broker['hostname'], broker['port'])
    beat = 'on' if env['BRV_BEAT'] == 'True' else 'off'
    clry_v = celery.__version__
    c_host = 'celery@bravo'
    regist = '%s regist' % len(insp.registered()[c_host])
    sched = '%s sched' % len(insp.scheduled()[c_host])

    celery_msg =\
    "%s-------------------------------- %scelery@bravo\n"      %(G,Y) +\
    "%s-------------------------------- %s%s\n"                %(G,G,str_brkr) +\
    "%s-------------------------------- %s[config]\n"          %(G,G) +\
    "%s-------------------------------- %s  > version: %s\n"   %(G,G,clry_v) +\
    "%s-------------------------------- %s  > workers: [%s]\n" %(G,G,n_workers) +\
    "%s-------------------------------- %s  > beat:    %s\n"   %(G,G,beat) +\
    "%s-------------------------------- %s  > tasks:   %s, %s\n"%(G,G,regist,sched) +\
    ""

    print bravo_msg + ENDC
    print celery_msg + ENDC
    mem = mem_check()

#-------------------------------------------------------------------------------
def set_environ(app):

    from config import SSL_CERT_PATH

    if not env.get('BRV_SANDBOX'):
        env['BRV_SANDBOX'] = 'False'

    env['BRV_HOSTNAME'] = hostname = socket.gethostname()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("gmail.com",80))
    except Exception as e:
        log.error('socket error connecting to gmail (desc: %s)', str(e))
        env['BRV_IP'] = 'False'
    else:
        env['BRV_IP'] = ip = s.getsockname()[0]
        s.close()

    try:
        domain = socket.gethostbyaddr(ip)[0]
    except Exception as e:
        log.warning('no domain found for host ip %s', ip)
        env['BRV_TEST'] = 'True'
        env['BRV_DOMAIN'] = 'False'
        env['BRV_SSL'] = 'False'
        env['BRV_HTTP_HOST'] = 'http://' + ip
        return
    else:
        env['BRV_DOMAIN'] = domain
        if domain == 'bravoweb.ca':
            log.debug('bravoweb.ca domain. deploy server')
            env['BRV_TEST'] = 'False'
        else:
            env['BRV_TEST'] = 'True'

    try:
        r = requests.get('https://%s' % domain, verify=True) #verify=SSL_CERT_PATH)
    except Exception as e:
        log.warning('warning: SSL not enabled. domain=%s', domain)
        log.debug('', exc_info=True)
        env['BRV_SSL'] = 'False'
        env['BRV_HTTP_HOST'] = 'http://' + env['BRV_DOMAIN']
    else:
        log.debug('SSL certificate verified. status code=%s', r.status_code)
        env['BRV_SSL'] = 'True'
        env['BRV_HTTP_HOST'] = 'https://' + env['BRV_DOMAIN']

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
