import json, logging
from flask import g, jsonify
from flask_login import login_required
from ..utils import print_vars
from . import main
from app.routing.tasks import *
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@main.route('/test_clean_sessions', methods=['GET'])
@login_required
def test_clean_sessions():
    from .. import tasks
    tasks.clean_expired_sessions.delay()
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/_analyze_routes', methods=['GET'])
@login_required
def _analyze_routes():
    rv = analyze_routes.apply(kwargs={'days':2})
    #log.debug(print_vars(rv))
    return jsonify({'state':rv.state, 'result':rv.result})

#-------------------------------------------------------------------------------
@main.route('/_build_routes', methods=['GET'])
@login_required
def _build_routes():
    rv = build_routes.apply(kwargs={})
    #log.debug(print_vars(rv))
    return jsonify({'state':rv.state, 'result':rv.result})

#-------------------------------------------------------------------------------
@main.route('/_schedule_reminders', methods=['GET'])
@login_required
def _schedule_reminders():
    from .. import tasks
    tasks.schedule_reminders.delay(queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/_non_participants', methods=['GET'])
@login_required
def _non_participants():
    from .. import tasks
    tasks.find_non_participants.delay(queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/_analyze_mobile/<days>', methods=['GET'])
@login_required
def _analyze_mobile(days):
    from .. import tasks
    tasks.update_sms_accounts.delay(
        kwargs={'days_delta':days},
        queue=current_app.config['DB'])
    return 'OK'
