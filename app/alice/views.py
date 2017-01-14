'''app.alice.views'''

import logging
from flask_login import login_required, current_user
from flask import g, request, jsonify, render_template, session, Response
from .. import get_db, utils
from app.utils import print_vars
from . import alice, incoming
from .session import store_sessions, dump_session, dump_sessions, wipe_sessions
from .incoming import make_reply
from .util import get_chatlogs
from .dialog import dialog
from .outgoing import send_welcome
from bson.objectid import ObjectId
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@alice.before_request
def alice_globals():
    g.db = get_db()

    if current_user.is_authenticated:
        log.debug('user authd')
        g.user = current_user
        g.agency = current_user.get_agency()

#-------------------------------------------------------------------------------
@alice.route('/', methods=['GET'])
@login_required
def show_chatlogs():
    return render_template('views/alice.html', admin=True)

#-------------------------------------------------------------------------------
@alice.route('/chatlogs', methods=['POST'])
@login_required
def _get_chatlogs():
    store_sessions()

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
    #log.debug(print_vars(request))
    a = utils.start_timer()

    try:
        response = incoming.receive()
    except Exception as e:
        log.debug(str(e), exc_info=True)
        log.debug(dump_session())
        log.error(str(e))
        return make_reply(dialog['error']['unknown'])

    utils.end_timer(a, display=True, lbl='alice request')

    return response

#-------------------------------------------------------------------------------
@alice.route('/send_welcome', methods=['POST'])
@login_required
def _send_welcome():

    try:
        r = send_welcome(request.json['etap_id'])
    except Exception as e:
        log.debug(str(e), exc_info=True)
        return Response(response=str(e), status_code=500)

    return jsonify(r)

#-------------------------------------------------------------------------------
@alice.route('/wipe_sessions', methods=['POST'])
@login_required
def _wipe_sessions():
    n = wipe_sessions()
    return jsonify('%s sessions wiped' % n)

#-------------------------------------------------------------------------------
@alice.route('/dump_sessions', methods=['POST'])
@login_required
def _dump_sessions():
    return jsonify(dump_sessions())
