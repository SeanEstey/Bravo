'''app.dt'''
import pytz
from datetime import datetime, date, time, timedelta

local_tz = pytz.timezone("Canada/Mountain")

#-------------------------------------------------------------------------------
def d_to_local_dt(d):
    return naive_to_local(datetime.combine(d, time(0,0,0)))

#-------------------------------------------------------------------------------
def local_today_dt():
    return naive_to_local(
        datetime.combine(
            date.today(),
            time(0,0,0)))

#-------------------------------------------------------------------------------
def naive_to_local(dt):
    return local_tz.localize(dt, is_dst=True)

#-------------------------------------------------------------------------------
def naive_utc_to_local(dt):
    '''dt contains UTC time but has no tz. add tz and convert'''
    return dt.replace(tzinfo=pytz.utc).astimezone(local_tz)

#-------------------------------------------------------------------------------
def tz_utc_to_local(dt):
    '''dt is tz-aware. convert time and tz'''
    return dt.astimezone(local_tz)

#-------------------------------------------------------------------------------
def localize(obj, to_strftime=None):
    '''Recursively scan through MongoDB document and convert all
    UTC datetimes to local time'''

    if isinstance(obj, dict):
        for k, v in obj.iteritems():
            obj[k] = localize(v, to_strftime=to_strftime)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            obj[idx] = localize(item, to_strftime=to_strftime)
    elif isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=pytz.utc)

        obj = obj.astimezone(local_tz)

        if to_strftime:
            obj = obj.strftime(to_strftime)

    return obj

#-------------------------------------------------------------------------------
def ddmmyyyy_to_dt(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy'''
    parts = ddmmyyyy.split('/')
    return datetime(int(parts[2]), int(parts[1]), int(parts[0]))

#-------------------------------------------------------------------------------
def ddmmyyyy_to_date(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy'''
    parts = ddmmyyyy.split('/')
    # Date constructor (year, month, day)
    return date(int(parts[2]), int(parts[1]), int(parts[0]))

#-------------------------------------------------------------------------------
def ddmmyyyy_to_local_dt(ddmmyyyy):
    '''@date_str: etapestry native dd/mm/yyyy'''
    parts = ddmmyyyy.split('/')
    return utils.naive_to_local(
        datetime(int(parts[2]), int(parts[1]), int(parts[0])))

#-------------------------------------------------------------------------------
def dt_to_ddmmyyyy(dt):
    return dt.strftime('%d/%m/%Y')

#-------------------------------------------------------------------------------
def ddmmyyyy_to_mmddyyyy(ddmmyyyy):
    p = ddmmyyyy.split('/')
    return '%s/%s/%s' % (p[1],p[0],p[2])
