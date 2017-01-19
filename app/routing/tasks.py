'''app.routing.tasks'''

import logging
from time import sleep
import bson.json_util
from flask import g
from flask_login import current_user
from dateutil.parser import parse
from datetime import datetime, date, time, timedelta
import re
from .. import get_keys, gcal, etap, utils, parser
from app.routing import depots
from app.tasks import celery_sio, celery
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def analyze_routes(self, days=None, **kwargs):
    '''Celery task
    Scans schedule for blocks, adds metadata to db, sends socketio signal
    to client
    '''

    print 'sleeping 3s...'
    sleep(3)

    celery_sio.emit(
        'analyze_routes', {'status':'in-progress'}, room=g.user.agency)

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

        if len(get_keys('routing')['locations']['depots']) > 1:
            depot = depots.resolve(block, postal)
        else:
            depot = get_keys('routing')['locations']['depots'][0]

        _route = {
          'block': block,
          'date': event_dt,
          'agency': g.user.agency,
          'status': 'pending',
          'postal': re.sub(r'\s', '', event['location']).split(','),
          'depot': depot,
          'driver': get_keys('routing')['drivers'][0], # default driver
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
            'add_route_metadata',
            {'data': utils.formatter(
                _route,
                to_strftime=True,
                bson_to_json=True)},
            room=g.user.agency)

    celery_sio.emit('analyze_routes', {'status':'completed'}, room=g.user.agency)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def build_routes(self, *args, **kwargs):
    '''Route orders for today's Blocks and build Sheets
    '''

    from app.routing import main
    from app.routing.schedule import analyze_upcoming
    from datetime import datetime, date, time
    from time import sleep

    agencies = g.db.agencies.find({})

    for agency in agencies:
        analyze_upcoming(agency['name'], 3)

        _routes = db.routes.find({
          'agency': agency['name'],
          'date': utils.naive_to_local(
            datetime.combine(
                date.today(),
                time(0,0,0)))
        })

        log.info(
          '%s: -----Building %s routes for %s-----',
          agency['name'], _routes.count(), date.today().strftime("%A %b %d"))

        successes = 0
        fails = 0

        for route in _routes:
            r = main.build(str(route['_id']))

            if not r:
                fails += 1
                log.error('Error building route %s', route['block'])
            else:
                successes += 1

            sleep(2)

        log.info(
            '%s: -----%s Routes built. %s failures.-----',
            agency['name'], successes, fails)

#-------------------------------------------------------------------------------
@celery.task(bind=True)
def build_route(self, *args, **kwargs):
    route_id = args[0]
    job_id=kwargs.get('job_id')

    try:
        from app.routing import main
        return main.build(str(route_id), job_id=job_id)
    except Exception as e:
        log.error('%s\n%s', str(e), tb.format_exc())
