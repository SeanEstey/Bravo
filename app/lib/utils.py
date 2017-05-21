'''app.lib.utils'''
import inspect, json, pytz, re, types
from pprint import pformat
from bson import json_util
from datetime import datetime, time, date
from .dt import to_local, local_tz, convert_obj

#-------------------------------------------------------------------------------
def inspector(obj, public=True, private=False):
    is_obj = (hasattr(obj, '__class__') and obj.__class__.__name__ or type(obj).__name__)

    if is_obj == False:
        return 'not an object. cant print'

    output = ''

    if public:
        name = obj.__class__.__name__
        if name == 'Flask':
            output += 'Public: %\n' % print_vars(obj, ignore=['url_map', 'view_functions'])
        elif name == 'Celery':
            output += 'Public: %s\n' % print_vars(obj, ignore=['_conf', '_tasks'])
        else:
            output += 'Public: %s\n' % print_vars(obj)

    if private:
        output += 'Private: %s' % pformat(vars(obj),indent=4)

    return output

#-------------------------------------------------------------------------------
def module_inspector(mylocals=False):
    if mylocals:
        _globals = globals().copy()
        _globals.pop('__builtins__')
        return print_vars(_globals,depth=1)

    for name, val in globals().items():
        print 'name=%s, val=%s' %(name, val)
        #if isinstance(val, types.ModuleType):
        #    #yield val.__name__
        #    print val.__name__

#-------------------------------------------------------------------------------
def print_vars(obj, depth=0, ignore=None, l="    "):
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
			return "[\n" + "\n".join(l + print_vars(
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
            print_vars(v, depth=depth-1, ignore=ignore, l=l+"  ") + \
            "," for k, v in objdict.iteritems()
        ) + "\n" + l + "}"

#-------------------------------------------------------------------------------
def dump(doc):
    return formatter(doc,
        to_local_time=True,
        to_strftime="%b %d, %H:%M %p",
        bson_to_json=True)

#-------------------------------------------------------------------------------
def formatter(doc, to_local_time=False, to_strftime=None, bson_to_json=False, to_json=False):
    '''@bson_to_json: convert ObjectIds->{'oid': 'string'}
    @to_local_time, to_strftime: convert utc datetimes to local time (and to
    string optionally)
    '''

    if to_local_time == True:
        doc = convert_obj(doc, to_tz=local_tz, to_str=to_strftime)

    if bson_to_json == True:
        no_bson = json_util.dumps(doc)

        if to_json:
            return no_bson
        else:
            return json.loads(no_bson)

    if to_json:
        return json.dumps(doc)

    return doc

#-------------------------------------------------------------------------------
def remove_quotes(s):
    s = re.sub(r'\"', '', s)
    return s

#-------------------------------------------------------------------------------
def to_title_case(s):
    s = re.sub(r'\"', '', s)
    s = re.sub(r'_', ' ', s)
    return s.title()

#-------------------------------------------------------------------------------
def start_timer():
    return datetime.now()

#-------------------------------------------------------------------------------
def end_timer(start_dt):
    b = datetime.now()
    c = b - start_dt
    seconds = '%s.%ss' % (c.seconds, str(c.microseconds/1000))
    return seconds
