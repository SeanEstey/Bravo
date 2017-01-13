'''app.alice.views'''

import logging
from flask_login import login_required, current_user
from flask import g, request, jsonify, render_template, session
from .. import get_db, utils
from . import alice, incoming
from .session import save_session
from .incoming import make_reply
from .util import get_chatlogs
from .dialog import dialog
from bson.objectid import ObjectId
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@alice.before_request
def alice_globals():
    g.db = get_db()

    if current_user.is_authenticated:
        g.user = current_user
        g.agency = current_user.get_agency()

#-------------------------------------------------------------------------------
@alice.route('/', methods=['GET'])
@login_required
def show_chatlogs():
    return render_template('views/alice.html')

#-------------------------------------------------------------------------------
@alice.route('/chatlogs', methods=['POST'])
@login_required
def _get_chatlogs():
    save_session()

    try:
        chatlogs = get_chatlogs()
    except Exception as e:
        log.debug(str(e))

    return jsonify(
        utils.formatter(
            chatlogs,
            to_local_time=True,
            bson_to_json=True))

#-------------------------------------------------------------------------------
@alice.route('/<agency>/receive', methods=['POST'])
def sms_received(agency):
    session['agency'] = agency

    a = utils.start_timer()

    try:
        response = incoming.receive()
    except Exception as e:
        log.debug(str(e), exc_info=True)
        log.error(str(e))
        return make_reply(dialog['error']['unknown'])

    utils.end_timer(a, display=True, lbl='alice request')

    return response
