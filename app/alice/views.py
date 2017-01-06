'''app.alice.views'''

import logging
from flask import request, jsonify, render_template
from flask_login import login_required, current_user
from .. import utils, db
from . import alice, helper
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
    agency = db.users.find_one({'user': current_user.username})['agency']

    chatlogs = helper.get_chatlogs(agency)

    return jsonify(
        utils.formatter(
            chatlogs,
            to_local_time=True,
            bson_to_json=True
        )
    )
