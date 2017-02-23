'''app.alice.views'''
import logging
from flask_login import login_required, current_user
from flask import g, request, jsonify, render_template, session, Response
from app import get_logger
from app.lib.utils import formatter, print_vars, start_timer, end_timer
from . import alice, incoming
from .session import store_sessions, dump_session, dump_sessions, wipe_sessions
from .incoming import make_reply
from .util import get_chatlogs
from .dialog import dialog
log = get_logger('alice.views')

#-------------------------------------------------------------------------------
@alice.before_request
def alice_globals():
    if current_user.is_authenticated:
        g.agency = current_user.agency

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
        formatter(
            chatlogs,
            to_local_time=True,
            bson_to_json=True))

#-------------------------------------------------------------------------------
@alice.route('/<agency>/receive', methods=['POST'])
def sms_received(agency):
    session['agency'] = agency
    #log.debug(print_vars(request))
    a = start_timer()

    try:
        response = incoming.receive()
    except Exception as e:
        log.error(str(e))
        log.debug('',exc_info=True)
        log.debug(dump_session())
        return make_reply(dialog['error']['unknown'])

    end_timer(a, lbl='alice request', to_log=log)

    return response

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
