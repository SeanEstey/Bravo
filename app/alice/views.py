'''app.alice.views'''

import logging
from flask import request, jsonify, render_template
from flask_login import login_required, current_user
from .. import get_db, utils
from . import alice, helper
from bson.objectid import ObjectId
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@alice.before_request
@login_required
def save_conversations():
    if request.method == 'GET':
        helper.save_conversations()

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

    try:
        chatlogs = helper.get_chatlogs(agency)
    except Exception as e:
        log.debug(str(e))

    return jsonify(
        utils.formatter(
            chatlogs,
            to_local_time=True,
            bson_to_json=True
        )
    )
