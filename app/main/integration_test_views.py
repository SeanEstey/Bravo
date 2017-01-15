
import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import g, request, jsonify, render_template, \
    redirect, Response, current_app, url_for
from flask_login import login_required, current_user
import logging
import bson.json_util
from . import main
from .. import get_db
from app.notify import pus
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@main.route('/test_clean_sessions', methods=['GET'])
@login_required
def test_clean_sessions():
    from .. import tasks
    tasks.clean_expired_sessions.apply_async(queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_task', methods=['GET'])
def test_test():
    logger.info('starting celery task')
    from .. import tasks
    tasks.test_test.apply_async(
        args=[3],
        queue=current_app.config['DB']
    )
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_schedule_reminders', methods=['GET'])
@login_required
def test_schedule_reminders():
    from .. import tasks
    tasks.schedule_reminders.apply_async(queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_non_participant', methods=['GET'])
@login_required
def test_non_participants():
    from .. import tasks
    tasks.find_non_participants.apply_async(queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_analyze_mobile/<days>', methods=['GET'])
@login_required
def test_analyze_mobile(days):
    from .. import tasks
    tasks.update_sms_accounts.apply_async(
        kwargs={'days_delta':days},
        queue=current_app.config['DB'])
    return 'OK'
