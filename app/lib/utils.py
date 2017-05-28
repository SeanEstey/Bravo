'''app.lib.utils'''
import gc, json, logging, os, re, types
from logging import getLogger
from datetime import datetime, time, date
from .dt import to_local, local_tz, convert_obj

log = getLogger(__name__)

#-------------------------------------------------------------------------------
def global_vars(deep=False):

    if deep:
        _globals = globals().copy()
        _globals.pop('__builtins__')
        return obj_vars(_globals,depth=1)

    _vars = ''

    for name, val in globals().items():
        _vars += 'name=%s, val=%s' %(name, val)

    return _vars

#-------------------------------------------------------------------------------
def obj_vars(obj, depth=0, ignore=None, l="    "):
    '''Print vars for any object.
    @depth: level of recursion
    @l: separator string
    '''

    #fall back to repr
    if depth<0: return repr(obj)
    #expand/recurse dict

    if isinstance(obj, dict):
        name = ""
        objdict = obj
    else:
        #if basic type, or list thereof, just print
        canprint=lambda o:isinstance(
            o,
            (int, float, str, unicode, bool, types.NoneType, types.LambdaType))

        try:
            if canprint(obj) or sum(not canprint(o) for o in obj) == 0:
                return repr(obj)
        except TypeError, e:
            pass

        # Try to iterate as if obj were a list

        try:
			return "[\n" + "\n".join(l + obj_vars(
				k, depth=depth-1, l=l+"  ") + "," for k in obj) + "\n" + l + "]"
        except TypeError, e:
            #else, expand/recurse object attribs

            objdict = {}
            name = \
                (hasattr(obj, '__class__') and \
                obj.__class__.__name__ or type(obj).__name__)


            for a in dir(obj):
                if a[:2] != "__" and (not hasattr(obj, a) or \
                not hasattr(getattr(obj, a), '__call__')):
                    try: objdict[a] = getattr(obj, a)
                    except Exception, e:
                        objdict[a] = str(e)

    if ignore:
        for ign in ignore:
            if ign in objdict.keys():
                objdict.pop(ign)

    return name + "{\n" + "\n"\
        .join(
            l + repr(k) + ": " + \
            obj_vars(v, depth=depth-1, ignore=ignore, l=l+"  ") + \
            "," for k, v in objdict.iteritems()
        ) + "\n" + l + "}"

#-------------------------------------------------------------------------------
def format_bson(obj, loc_time=False, dt_str=None, to_json=False):
    '''Make BSON obj vars printable (default) or to JSON str.
    @to_json: convert to str (BSON.date->{'$date':<timestamp str>})
    @loc_time: UTC dt to localized tz dt
    @dt_str: BSON->Date to strftime formatted str
    '''

    if loc_time == True or dt_str:
        obj = convert_obj(obj, to_tz=local_tz, to_str=dt_str)

    from bson import json_util

    if to_json == True:
        return json_util.dumps(obj)
    else:
        return json.loads(json_util.dumps(obj))

#-------------------------------------------------------------------------------
def dump_bson(obj):
    '''BSON obj->JSON str'''

    return format_bson(obj,
        loc_time=True,
        dt_str="%b %d, %H:%M %p",
        to_json=True)

#-------------------------------------------------------------------------------
def mem_check():

    import psutil
    mem = psutil.virtual_memory()
    total = (mem.total/1000000)
    free = mem.free/1000000

    if free < 350:
        log.debug('low memory. %s/%s. forcing gc/clearing cache...', free, total)
        os.system('sudo sysctl -w vm.drop_caches=3')
        os.system('sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches')
        gc.collect()
        mem = psutil.virtual_memory()
        total = (mem.total/1000000)
        now_free = mem.free/1000000
        log.debug('freed %s mb', now_free - free)

        if free < 350:
            log.warning('warning: low memory! 250mb recommended (%s/%s)', free, total)

    return mem

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


