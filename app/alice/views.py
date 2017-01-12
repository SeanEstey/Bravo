'''app.alice.views'''

import logging
from flask_login import login_required, current_user
from flask import g, request, jsonify, render_template
from .. import get_db, utils
from . import alice, helper, incoming
from bson.objectid import ObjectId
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@alice.before_request
def alice_globals():
    g.db = get_db()

    if current_user.is_authenticated:
        g.user = current_user
        g.agency = current_user.get_agency()
        log.debug('user agency=%s', g.agency)

#-------------------------------------------------------------------------------
@alice.route('/', methods=['GET'])
@login_required
def show_chatlogs():
    return render_template('views/alice.html')

#-------------------------------------------------------------------------------
@alice.route('/chatlogs', methods=['POST'])
@login_required
def get_chatlogs():
    helper.save_conversations()

    try:
        chatlogs = helper.get_chatlogs(g.agency)
    except Exception as e:
        log.debug(str(e))

    return jsonify(
        utils.formatter(
            chatlogs,
            to_local_time=True,
            bson_to_json=True))

#-------------------------------------------------------------------------------
@alice.route('/receive', methods=['POST'])
def sms_received():
    a = utils.start_timer()
    response = incoming.receive()
    utils.end_timer(a, display=True, lbl='alice request')

    return response
