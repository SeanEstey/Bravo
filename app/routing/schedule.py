'''app.routing.schedule'''

import logging
import bson.json_util
from flask import g
from flask_login import current_user
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
import re
from .. import get_keys, gcal, etap, wsf, utils, parser
from app.tasks import celery_sio
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def analyze_upcoming(days):
    '''Celery task
    Scans schedule for blocks, adds metadata to db, sends socketio signal
    to client
    '''

    celery_sio.emit(
        'room_msg',
        {'msg': 'analyze_routes', 'status':'in-progress'},
        room=g.user.agency)

    today_dt = datetime.combine(date.today(), time())
    end_dt = today_dt + timedelta(days=int(days))
    events = []
    service = gcal.gauth(get_keys('google')['oauth'])
    cal_ids = get_keys('cal_ids')

    for _id in cal_ids:
        events += gcal.get_events(
            service,
            cal_ids[_id],
            today_dt,
            end_dt
        )

    events = sorted(events, key=lambda k: k['start'].get('date'))

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

        if g.db.routes.find_one({
            'date':event_dt,
            'block': block,
            'agency':g.user.agency}
        ):
            continue

        # Build route metadata

        # 1.a Let's grab info from eTapestry
        try:
            a = etap.call(
              'get_query_accounts',
              get_keys('etapestry'), {
                'query':block,
                'query_category': get_keys('etapestry')['query_category']}
            )
        except Exception as e:
            log.error('Error retrieving accounts for query %s', block)
            #if 'count' not in a:
            log.error('No accounts found in query %s', block)
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
        if len(get_keys('routing')['locations']['depots']) > 1:
            depot = wsf.resolve_depot(block, postal)
        else:
            depot = get_keys('routing')['locations']['depots'][0]

        _route = {
          'block': block,
          'date': event_dt,
          'agency': g.user.agency,
          'status': 'pending',
          'postal': re.sub(r'\s', '', event['location']).split(','),
          'depot': depot,
          'driver': ge_keys('routing')['drivers'][0], # default driver
          'orders': num_booked,
          'block_size': len(a['data']),
          'dropoffs': num_dropoffs
        }

        g.db.routes.insert_one(_route)

        log.info(
            'metadata added for %s on %s',
            _route['block'], _route['date'].strftime('%b %-d'))

        # Send it to the client
        celery_sio.emit(
            'room_msg', {
                'msg':'add_route_metadata',
                'data': utils.formatter(
                    _route,
                    to_strftime=True,
                    bson_to_json=True)},
            room=g.user.agency)

    celery_sio.emit('room_msg',
        {'msg':'analyze_routes', 'status':'completed'},
        room=g.user.agency)

    return True
