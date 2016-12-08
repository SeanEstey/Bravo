'''booker.views'''

import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import request, jsonify, render_template, redirect, current_app,url_for
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import logging

from . import booker
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

    response = book.make(
        user['agency'],
        request.form['aid'],
        request.form['block'],
        request.form['date'],
        request.form['driver_notes'],
        request.form['name'],
        request.form['email'],
        request.form['confirmation'] == 'true'
    )

    return jsonify(response)

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
    tasks.update_map_data.apply_async(
        kwargs={'agency': user['agency'] },
        queue=current_app.config['DB']
    )
    return jsonify('OK')
