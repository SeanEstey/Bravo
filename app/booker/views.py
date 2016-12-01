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
from . import search
from .. import utils
from .. import db
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@booker.route('/', methods=['GET'])
@login_required
def show_home():
    agency = db['users'].find_one({'user': current_user.username})['agency']
    return render_template('views/booker.html', agency=agency)

#-------------------------------------------------------------------------------
@booker.route('/search', methods=['POST'])
@login_required
def submit_search():
    logger.info(request.form.to_dict())

    user = db.users.find_one({'user': current_user.username})

    results = search.search(
        db.agencies.find_one({'name':user['agency']})['name'],
        request.form['query']
    )

    return jsonify(results)
