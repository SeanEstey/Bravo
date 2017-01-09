'''app.alice.views'''

import logging
from flask import request, jsonify, render_template, session
from flask_login import login_required, current_user
from .. import get_db, utils
from . import alice, helper
from bson.objectid import ObjectId
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@alice.route('/', methods=['GET'])
@login_required
def show_chatlogs():
    return render_template('views/alice.html')

#-------------------------------------------------------------------------------
@alice.route('/chatlogs', methods=['POST'])
@login_required
def get_chatlogs():
    db = get_db()

    agency = db.users.find_one({'user': current_user.username})['agency']

    chatlogs = helper.get_chatlogs(agency)

    return jsonify(
        utils.formatter(
            chatlogs,
            to_local_time=True,
            bson_to_json=True
        )
    )
