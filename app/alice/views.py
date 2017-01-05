'''alice.views'''

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
@alice.route('/')
@login_required
def show_chatlogs():
    return render_template('views/alice.html')

#-------------------------------------------------------------------------------
@alice.route('/chatlogs', methods=['POST'])
def get_chatlogs():
    agency = db.users.find_one({'user': current_user.username})['agency']

    chatlogs = alice.get_chatlogs(agency)

    return jsonify(
        utils.formatter(
            chatlogs,
            to_local_time=True,
            bson_to_json=True
        )
    )
