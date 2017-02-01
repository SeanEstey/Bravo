'''app.dt'''
import logging, pytz
from datetime import datetime, date, time, timedelta
local_tz = pytz.timezone('MST')
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def to_utc(obj=None, dt=None, d=None, t=None, to_str=False):
    if obj:
        return convert_obj(obj, to_tz=pytz.utc, to_str=to_str)
    else:
        return to_timezone(pytz.utc, dt=dt, d=d, t=t, to_str=to_str)

#-------------------------------------------------------------------------------
def to_local(obj=None, dt=None, d=None, t=None, to_str=False):
    if obj:
        return convert_obj(obj, to_tz=local_tz, to_str=to_str)
    else:
        return to_timezone(local_tz, dt=dt, d=d, t=t, to_str=to_str)

#-------------------------------------------------------------------------------
def to_timezone(tz, dt=None, d=None, t=None, to_str=False):
    if dt:
        dt = dt.replace(tzinfo=tz) if not dt.tzinfo else dt.astimezone(tz)
        return dt.strftime(to_str) if to_str else dt
    elif d and t:
        dt_ = datetime.combine(d,t)
        dt_ = dt_.replace(tzinfo=tz) if not dt_.tzinfo else dt_.astimezone(tz)
        return dt_.strftime(to_str) if to_str else dt_
    elif d and not t:
        dt_ = datetime.combine(d, time(0,0))
        dt_ = dt.replace(tzinfo=tz) if not dt_.tzinfo else dt_.astimezone(tz)
        return dt_.strftime(to_str) if to_str else dt_

#-------------------------------------------------------------------------------
def convert_obj(obj, to_tz=None, to_str=False):
    '''Returns a datetime with given timezone. Will convert timezones for
    non-naive datetimes
    @obj: any data structure (dict, list, etc)
    '''

    #log.debug('convert obj=%s, to_tz=%s, to_str=%s', obj, to_tz, to_str)

    if isinstance(obj, dict):
        for k, v in obj.iteritems():
            obj[k] = convert_obj(v, to_str=to_str, to_tz=tz)
        return obj
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            obj[idx] = convert_obj(item, to_str=to_str, to_tz=tz)
        return obj
    elif isinstance(obj, datetime):
        tz = to_tz if to_tz else local_tz
        obj = obj.replace(tzinfo=tz) if not obj.tzinfo else obj.astimezone(tz)
        return obj.strftime(to_str) if to_str else obj

#-------------------------------------------------------------------------------
def _local_today_dt():
    return naive_to_local(datetime.combine(
        date.today(),
        time(0,0,0)))

#-------------------------------------------------------------------------------
def _naive_to_local(dt):
    return local_tz.localize(dt, is_dst=True)

#-------------------------------------------------------------------------------
def _naive_utc_to_local(dt):
    '''dt contains UTC time but has no tz. add tz and convert
    '''
    return dt.replace(tzinfo=pytz.utc).astimezone(local_tz)

#-------------------------------------------------------------------------------
def _tz_utc_to_local(dt):
    '''dt is tz-aware. convert time and tz
    '''
    return dt.astimezone(local_tz)

#-------------------------------------------------------------------------------
def ddmmyyyy_to_dt(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy
    '''
    parts = ddmmyyyy.split('/')
    return datetime(int(parts[2]), int(parts[1]), int(parts[0]))

#-------------------------------------------------------------------------------
def ddmmyyyy_to_date(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy
    '''
    parts = ddmmyyyy.split('/')
    return date(int(parts[2]), int(parts[1]), int(parts[0]))

#-------------------------------------------------------------------------------
def ddmmyyyy_to_local_dt(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy
    '''
    parts = ddmmyyyy.split('/')
    return naive_to_local(
        datetime(int(parts[2]), int(parts[1]), int(parts[0])))

#-------------------------------------------------------------------------------
def dt_to_ddmmyyyy(dt):
    return dt.strftime('%d/%m/%Y')

#-------------------------------------------------------------------------------
def ddmmyyyy_to_mmddyyyy(ddmmyyyy):
    p = ddmmyyyy.split('/')
    return '%s/%s/%s' % (p[1],p[0],p[2])
