'''app.dt'''
import pytz
from datetime import datetime, date, time, timedelta
local_tz = pytz.timezone("Canada/Mountain")

def localize(obj, date_=None, time_=None, to_str=None):
    '''Convert all datetimes to local timezone time
    @obj: any data structure (dict, list, etc)
    '''

    if date_ and time_:
        return localize(datetime.combine(date_, time_))
    elif date_ and not time_:
        return localize(datetime.combine(date_, time(0,0)))

    if isinstance(obj, dict):
        for k, v in obj.iteritems():
            obj[k] = localize(v, to_str=to_str)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            obj[idx] = localize(item, to_str=to_str)
    elif isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=pytz.utc)

        obj = obj.astimezone(local_tz)

        if to_str:
            obj = obj.strftime(to_str)

    return obj

def to_localized_dt(datetime_=None, date_=None, time_=None):
    '''
    '''

    if datetime_:
        return naive_to_local(datetime_)

    if date_ and not time_:
        return localize(datetime.combine(date_, time(0,0,0)))
    elif date_ and time_:
        return localize(datetime.combine(date_, time_))
    else:
        return localize(datetime.combine(
            date.today(),
            time(0,0,0)))

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
