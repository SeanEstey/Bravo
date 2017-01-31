'''app.dt'''
import logging, pytz
from datetime import datetime, date, time, timedelta
local_tz = pytz.timezone('MST')
log = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def to_utc(obj, date_=None, time_=None, to_str=None):
    return _convert(obj, date_=date_, time_=time_, to_str=to_str, to_tz=pytz.utc)

#-------------------------------------------------------------------------------
def to_local(obj, date_=None, time_=None, to_str=None):
    return _convert(obj, date_=date_, time_=time_, to_str=to_str, to_tz=local_tz)

#-------------------------------------------------------------------------------
def _convert(obj, date_=None, time_=None, to_str=None, to_tz=None):
    '''Returns a datetime with given timezone. Will convert timezones for
    non-naive datetimes
    @obj: any data structure (dict, list, etc)
    '''

    #log.debug('localize obj=%s, date_=%s, time=%s, to_tz=%s', obj, date_, time_, to_tz)
    tz = to_tz
    if not to_tz:
        tz = local_tz

    if date_ and time_:
        return _convert(datetime.combine(date_, time_))
    elif date_ and not time_:
        return _convert(datetime.combine(date_, time(0,0)))

    if isinstance(obj, dict):
        for k, v in obj.iteritems():
            obj[k] = _convert(v, to_str=to_str)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            obj[idx] = _convert(item, to_str=to_str)
    elif isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=tz)
        else:
            obj = obj.astimezone(tz)

        if to_str:
            obj = obj.strftime(to_str)

    return obj

def _local_today_dt():
    return naive_to_local(datetime.combine(
        date.today(),
        time(0,0,0)))

def _naive_to_local(dt):
    return local_tz.localize(dt, is_dst=True)

def _naive_utc_to_local(dt):
    '''dt contains UTC time but has no tz. add tz and convert
    '''
    return dt.replace(tzinfo=pytz.utc).astimezone(local_tz)

def _tz_utc_to_local(dt):
    '''dt is tz-aware. convert time and tz
    '''
    return dt.astimezone(local_tz)

def ddmmyyyy_to_dt(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy
    '''
    parts = ddmmyyyy.split('/')
    return datetime(int(parts[2]), int(parts[1]), int(parts[0]))

def ddmmyyyy_to_date(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy
    '''
    parts = ddmmyyyy.split('/')
    return date(int(parts[2]), int(parts[1]), int(parts[0]))

def ddmmyyyy_to_local_dt(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy
    '''
    parts = ddmmyyyy.split('/')
    return naive_to_local(
        datetime(int(parts[2]), int(parts[1]), int(parts[0])))

def dt_to_ddmmyyyy(dt):
    return dt.strftime('%d/%m/%Y')

def ddmmyyyy_to_mmddyyyy(ddmmyyyy):
    p = ddmmyyyy.split('/')
    return '%s/%s/%s' % (p[1],p[0],p[2])
