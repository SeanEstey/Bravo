'''app.alice.views'''
import logging
from flask_login import login_required, current_user
from flask import g, jsonify, render_template, session
from . import alice, incoming
from .session import archive_chats, dump_session, dump_sessions, wipe_sessions
from .incoming import make_reply
from .dialog import dialog
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@alice.before_request
def alice_globals():
    # TODO: Delete this??
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
def view_chatlogs():

    from .util import get_chatlogs
    archive_chats()

    try:
        chatlogs_json = get_chatlogs(serialize=True)
    except Exception as e:
        log.exception('Error retrieving Alice chats: %s', e.message)
        raise
    else:
        return jsonify(chatlogs_json)

#-------------------------------------------------------------------------------
@alice.route('/<agency>/receive', methods=['POST'])
def sms_received(agency):

    session['agency'] = agency

    try:
        response = incoming.receive()
    except Exception as e:
        log.exception('Error receiving SMS', extra={'session':dump_session()})
        return make_reply(dialog['error']['unknown'])

    return response

#-------------------------------------------------------------------------------
@alice.route('/wipe_sessions', methods=['GET', 'POST'])
@login_required
def _wipe_sessions():
    n = wipe_sessions()
    return jsonify('%s sessions wiped' % n)

#-------------------------------------------------------------------------------
@alice.route('/dump_sessions', methods=['POST'])
@login_required
def _dump_sessions():
    return jsonify(dump_sessions())
