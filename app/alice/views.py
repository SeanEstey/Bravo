'''app.alice.views'''
import logging
from flask_login import login_required, current_user
from flask import g, jsonify, render_template, session
from . import alice, incoming
from .session import dump_session, wipe_sessions
from .incoming import make_reply
from .dialog import dialog
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@alice.route('/', methods=['GET'])
@login_required
def show_chatlogs():
    return render_template('views/alice.html', admin=True)

#-------------------------------------------------------------------------------
@alice.route('/<group>/receive', methods=['POST'])
def sms_received(group):

    session['group'] = group

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

