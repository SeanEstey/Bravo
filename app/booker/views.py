'''booker.views'''
import logging
from datetime import datetime, date, time, timedelta
from flask import g, request, jsonify, render_template
from flask_login import login_required
from . import booker, geo
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@booker.route('/', methods=['GET'])
@login_required
def show_home():
    return render_template(
        'views/booker.html',
        admin=g.user.admin,
        agency=g.user.agency)

#-------------------------------------------------------------------------------
@booker.route('/find_nearby_blocks', methods=['POST'])
def find_nearby_blocks():
    maps = g.db.maps.find_one({'agency':g.user.agency})['features']

    SEARCH_WEEKS = 12
    SEARCH_DAYS = SEARCH_WEEKS * 7
    SEARCH_RADIUS = float(request.form['radius'])

    events = []
    end_date = datetime.today() + timedelta(days=SEARCH_DAYS)

    service = gcal.gauth(get_keys('google')['oauth'])
    cal_ids = get_keys('cal_ids')

    for _id in cal_ids:
        events +=  gcal.get_events(
            service,
            cal_ids[_id],
            datetime.today(),
            end_date)

    events =sorted(
        events,
        key=lambda k: k['start'].get('dateTime',k['start'].get('date')))

    pt = {'lng': request.form['lng'], 'lat': request.form['lat']}

    results = geo.get_nearby_blocks(pt, SEARCH_RADIUS, maps, events)

    return jsonify(results)
