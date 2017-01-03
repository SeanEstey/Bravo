'''booker.views'''

import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import request, jsonify, render_template, redirect, current_app,url_for
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import logging

from . import booker, geo
from . import search, book
from .. import utils
from .. import db
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@booker.route('/', methods=['GET'])
@login_required
def show_home():
    agency = db['users'].find_one({'user': current_user.username})['agency']

    return render_template(
        'views/booker.html',
        admin=True,
        agency=agency)

#-------------------------------------------------------------------------------
@booker.route('/search', methods=['POST'])
@login_required
def submit_search():
    logger.info(request.form.to_dict())

    user = db.users.find_one({'user': current_user.username})

    results = search.search(
        db.agencies.find_one({'name':user['agency']})['name'],
        request.form['query'],
        request.form.get('radius'),
        request.form.get('weeks')
    )

    return jsonify(results)


#-------------------------------------------------------------------------------
@booker.route('/find_nearby_blocks', methods=['POST'])
def find_nearby_blocks():

    conf = db.agencies.find_one({'name':request.form['agency']})
    maps = db.maps.find_one({'agency':conf['name']})['features']

    SEARCH_WEEKS = 12
    SEARCH_DAYS = SEARCH_WEEKS * 7
    SEARCH_RADIUS = float(request.form['radius'])

    events = []
    end_date = datetime.today() + timedelta(days=SEARCH_DAYS)

    service = gcal.gauth(conf['google']['oauth'])

    for cal_id in conf['cal_ids']:
        events +=  gcal.get_events(
            service,
            conf['cal_ids'][cal_id],
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
    user = db.users.find_one({'user': current_user.username})

    response = search.get_account(
        user['agency'],
        request.form['aid']
    )

    return jsonify(response)

#-------------------------------------------------------------------------------
@booker.route('/book', methods=['POST'])
@login_required
def do_booking():
    logger.debug(request.form.to_dict())

    user = db.users.find_one({'user': current_user.username})

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
    user = db.users.find_one({'user': current_user.username})
    maps = db.maps.find_one({'agency':user['agency']})

    return jsonify(
        utils.formatter(
            maps,
            bson_to_json=True
        )
    )

#-------------------------------------------------------------------------------
@booker.route('/update_maps', methods=['POST'])
@login_required
def update_maps():
    user = db.users.find_one({'user': current_user.username})

    from .. import tasks
    tasks.update_maps.apply_async(
        kwargs={
            'agency': user['agency'],
            'emit_status': True
        },
        queue=current_app.config['DB'])

    return jsonify('OK')
