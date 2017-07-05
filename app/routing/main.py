'''app.routing.main'''
import json, re, pytz
from dateutil.parser import parse
from datetime import datetime, time, date
from flask import g, request
from bson import ObjectId as oid
from app import get_keys
from app.lib import gsheets
from app.lib.utils import format_bson
from app.lib.dt import ddmmyyyy_to_date
from app.main.etapestry import EtapError, get_udf, get_query
from . import depots
from logging import getLogger
log = getLogger(__name__)

'''Methods called either from client user or celery task. g.group set'''

#-------------------------------------------------------------------------------
def is_scheduled(acct, date_):

    # Ignore accts with Next Pickup > today
    next_pickup = get_udf('Next Pickup Date', acct)

    if next_pickup:
        np = next_pickup.split('/')
        next_pickup = parse('/'.join([np[1], np[0], np[2]])).date()

    next_delivery = get_udf('Next Delivery Date', acct)

    if next_delivery:
        nd = next_delivery.split('/')
        next_delivery = parse('/'.join([nd[1], nd[0], nd[2]])).date()

    if next_pickup and next_pickup > date_ and not next_delivery:
        return False
    elif next_delivery and next_delivery != date_ and not next_pickup:
        return False
    elif next_pickup and next_delivery and next_pickup > date_ and next_delivery != date_:
        return False

    return True

#-------------------------------------------------------------------------------
def get_metadata():
    '''Get metadata for routes today and onward
    '''

    docs = g.db.routes.find({
        'agency': g.group,
        'date': {'$gte':datetime.combine(date.today(),time())}
    }).sort('date', 1)

    docs = format_bson(list(docs), loc_time=True, dt_str="%A %b %d")

    for route in docs:
        # for storing in route_btn.attr('data-route')
        route['json'] = json.dumps(route)

    return docs

#-------------------------------------------------------------------------------
def add_metadata(block, event_dt, event):

    try:
        accts = get_query(block)
    except EtapError as e:
        #log.error('Error retrieving query=%s', block)
        raise

    n_drops = n_booked = 0

    for acct in accts:
        npu = get_udf('Next Pickup Date', acct)

        if npu == '':
            continue

        npu_d = ddmmyyyy_to_date(npu)

        if npu_d == event_dt.date():
            n_booked += 1

        if get_udf('Status', acct) == 'Dropoff':
            n_drops += 1

    postal = ''
    if event.get('location'):
        postal = re.sub(r'\s', '', event['location']).split(',')

    if len(get_keys('routing')['locations']['depots']) > 1:
        depot = depots.resolve(block, postal)
    else:
        depot = get_keys('routing')['locations']['depots'][0]

    meta = {
      'block': block,
      'date': event_dt.astimezone(pytz.utc),
      'agency': g.group,
      'status': 'pending',
      'postal': postal,
      'depot': depot,
      'driver': get_keys('routing')['drivers'][0], # default driver
      'orders': n_booked,
      'block_size': len(accts),
      'dropoffs': n_drops}

    g.db.routes.insert_one(meta)

    return meta

#-------------------------------------------------------------------------------
def edit_field(route_id, field, value):

    log.debug('edit_route id=%s, field=%s, value=%s',route_id,field,value)

    value_type = None

    if field == 'depot':
        for depot in get_keys('routing')['locations']['depots']:
            if depot['name'] == value:
                g.db.routes.update_one(
                    {'_id':oid(route_id)},
                    {'$set': {'depot':depot}})
                return 'success'
    elif field == 'driver':
        for driver in get_keys('routing')['drivers']:
            if driver['name'] == value:
                g.db.routes.update_one(
                    {'_id':oid(route_id)},
                    {'$set': {'driver':driver}})
                return 'success'

    log.error('couldnt find value in db for %s:%s', field, value)
    return 'failed'
