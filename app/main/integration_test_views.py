
import json
import logging
from datetime import datetime, date, time, timedelta
from flask import g, request, jsonify, render_template, \
    redirect, Response, current_app, url_for
from flask_login import login_required, current_user
from . import main
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@main.route('/test_clean_sessions', methods=['GET'])
@login_required
def test_clean_sessions():
    from .. import tasks
    tasks.clean_expired_sessions.delay()
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_task', methods=['GET'])
def test_test():
    #log.info('starting celery task from request')

    from app.tasks import test_trig
    test_trig.delay(
        args=[{'NAME': 'SEAN_ESTEY'}],
        kwargs={'a':'b'},
        queue='bravo'
    )
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_schedule_reminders', methods=['GET'])
@login_required
def test_schedule_reminders():
    from .. import tasks
    tasks.schedule_reminders.delay(queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_non_participant', methods=['GET'])
@login_required
def test_non_participants():
    from .. import tasks
    tasks.find_non_participants.delay(queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_analyze_mobile/<days>', methods=['GET'])
@login_required
def test_analyze_mobile(days):
    from .. import tasks
    tasks.update_sms_accounts.delay(
        kwargs={'days_delta':days},
        queue=current_app.config['DB'])
    return 'OK'
