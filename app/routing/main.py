'''app.routing.main'''
import json, logging, re, pytz
from dateutil.parser import parse
from datetime import datetime, time, date
from flask import g, request
from bson import ObjectId
from app import smart_emit, get_keys, gsheets, cal, utils
from app.etap import EtapError, get_udf, get_query
from app.utils import print_vars, formatter
from app.dt import ddmmyyyy_to_date
from . import depots
log = logging.getLogger(__name__)
class GeocodeError(Exception):
    pass

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
        'agency': g.user.agency,
        'date': {'$gte':datetime.combine(date.today(),time())}
    }).sort('date', 1)

    docs = formatter(
        list(docs),
        bson_to_json=True,
        to_local_time=True,
        to_strftime="%A %b %d")

    for route in docs:
        # for storing in route_btn.attr('data-route')
        route['json'] = json.dumps(route)

    return docs

#-------------------------------------------------------------------------------
def add_metadata(agcy, block, event_dt, event):

    try:
        accts = get_query(block, get_keys('etapestry',agcy=agcy))
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

    if len(get_keys('routing', agcy=agcy)['locations']['depots']) > 1:
        depot = depots.resolve(block, postal)
    else:
        depot = get_keys('routing', agcy=agcy)['locations']['depots'][0]

    meta = {
      'block': block,
      'date': event_dt.astimezone(pytz.utc),
      'agency': agcy,
      'status': 'pending',
      'postal': postal,
      'depot': depot,
      'driver': get_keys('routing', agcy=agcy)['drivers'][0], # default driver
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
                value_type = depot
    elif field == 'driver':
        for driver in get_keys('routing')['drivers']:
            if driver['name'] == value:
                value_type = driver

    if not value_type:
        log.error('couldnt find value in db for %s:%s', field, value)
        return 'failed'

    g.db.routes.update_one(
        {'_id':ObjectId(route_id)},
        {'$set': {field:value}})

    return 'success'
