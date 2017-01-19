'''booker.views'''

import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import g, request, jsonify, render_template, redirect, current_app,url_for
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import logging
from . import booker, geo, search, book
from .. import utils
from .tasks import update_maps
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@booker.route('/', methods=['GET'])
@login_required
def show_home():
    return render_template(
        'views/booker.html',
        admin=g.user.admin,
        agency=g.user.agency)

#-------------------------------------------------------------------------------
@booker.route('/search', methods=['POST'])
@login_required
def submit_search():
    logger.info(request.form.to_dict())

    results = search.search(
        g.user.agency,
        request.form['query'],
        request.form.get('radius'),
        request.form.get('weeks')
    )

    return jsonify(results)

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
            end_date
        )

    events =sorted(
        events,
        key=lambda k: k['start'].get('dateTime',k['start'].get('date'))
    )

    pt = {'lng': request.form['lng'], 'lat': request.form['lat']}

    results = geo.get_nearby_blocks(pt, SEARCH_RADIUS, maps, events)

    return jsonify(results)

#-------------------------------------------------------------------------------
@booker.route('/get_acct', methods=['POST'])
@login_required
def get_acct():
    response = search.get_account(
        g.user.agency,
        request.form['aid']
    )

    return jsonify(response)

#-------------------------------------------------------------------------------
@booker.route('/book', methods=['POST'])
@login_required
def do_booking():
    logger.debug(request.form.to_dict())

    user = g.db.users.find_one({'user': current_user.user_id})

    data = {
        'aid': request.form['aid'],
        'block': request.form['block'],
        'date': request.form['date'],
        'driver_notes': request.form['driver_notes'],
        'name': request.form['name'],
        'email': request.form['email'],
        'send_confirm': request.form['confirmation'] == 'true',
        'user_fname': user['name']
    }

    return jsonify(book.make(user['agency'], data))

#-------------------------------------------------------------------------------
@booker.route('/get_maps', methods=['POST'])
@login_required
def get_maps():
    return jsonify(utils.formatter(
        g.db.maps.find_one({'agency':g.user.agency}),
        bson_to_json=True))

#-------------------------------------------------------------------------------
@booker.route('/update_maps', methods=['POST'])
@login_required
def update_maps():
    update_maps.async(kwargs={'agency': g.user.agency, 'emit_status': True})

    return jsonify('OK')
