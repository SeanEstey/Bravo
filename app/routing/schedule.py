'''app.routing.schedule'''

import logging
import bson.json_util
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
import re

from app import db
from app import task_emit
from .. import gcal, etap, wsf, utils, parser

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def analyze_upcoming(agency_name, days):
    agency = db.agencies.find_one({'name':agency_name})
    conf = db.agencies.find_one({'name':agency['name']})['routing']
    cal_ids = db.agencies.find_one({'name':agency['name']})['cal_ids']
    oauth = db.agencies.find_one({'name':agency['name']})['google']['oauth']

    today_dt = datetime.combine(date.today(), time())
    end_dt = today_dt + timedelta(days=int(days))
    events = []

    for _id in cal_ids:
        events += gcal.get_events(gcal.gauth(oauth), cal_ids[_id], today_dt, end_dt)

    events = sorted(events, key=lambda k: k['start'].get('date'))

    n=0

    task_emit('analyze_routes', {'status':'in-progress'})
    #from ../socketio import socketio_app
    #socketio_app.emit('analyze_routes', {'status':'in-progress'})

    for event in events:
        block = parser.get_block(event['summary'])

        if not block:
            continue

        # yyyy-mm-dd format
        event_dt = utils.naive_to_local(
            datetime.combine(
                parse(event['start']['date']),
                time(0,0,0))
        )

        if db.routes.find_one({'date':event_dt, 'block': block, 'agency':agency['name']}):
            continue

        # Build route metadata

        # 1.a Let's grab info from eTapestry
        etap_conf = db.agencies.find_one({'name':agency['name']})['etapestry']

        try:
            a = etap.call(
              'get_query_accounts',
              etap_conf,
              {'query':block, 'query_category':etap_conf['query_category']}
            )
        except Exception as e:
            logger.error('Error retrieving accounts for query %s', block)

        if 'count' not in a:
            logger.error('No accounts found in query %s', block)
            continue

        num_dropoffs = 0
        num_booked = 0

        event_d = event_dt.date()

        for account in a['data']:
            npu = etap.get_udf('Next Pickup Date', account)

            if npu == '':
                continue

            npu_d = etap.ddmmyyyy_to_date(npu)

            if npu_d == event_d:
                num_booked += 1

            if etap.get_udf('Status', account) == 'Dropoff':
                num_dropoffs += 1

        postal = re.sub(r'\s', '', event['location']).split(',')

        # TODO: move resolve_depot into depots.py module
        if len(conf['locations']['depots']) > 1:
            depot = wsf.resolve_depot(block, postal)
        else:
            depot = conf['locations']['depots'][0]

        _route = {
          'block': block,
          'date': event_dt,
          'agency': agency['name'],
          'status': 'pending',
          'postal': re.sub(r'\s', '', event['location']).split(','),
          'depot': depot,
          'driver': conf['drivers'][0], # default driver
          'orders': num_booked,
          'block_size': len(a['data']),
          'dropoffs': num_dropoffs
        }

        db['routes'].insert_one(_route)

        logger.info(
            'metadata added for %s on %s',
            _route['block'], _route['date'].strftime('%b %-d'))

        # Send it to the client
        task_emit('add_route_metadata', data=utils.formatter(
            _route,
            to_strftime=True,
            bson_to_json=True))

        n+=1

    task_emit('analyze_routes', {'status':'completed'})

    return True
