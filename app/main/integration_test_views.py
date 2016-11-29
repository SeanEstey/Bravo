
import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import request, jsonify, render_template, \
    redirect, Response, current_app, url_for
from flask_login import login_required, current_user
import logging
import bson.json_util

from . import main
from app.notify import pus
from .. import db
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@main.route('/test_master_sms_enable', methods=['GET'])
@login_required
def test_master_sms_enable():
    from .. import tasks

    for d in range(18,50):
        tasks.update_sms_accounts.apply_async(
                kwargs={'days_delta':d, 'agency_name':'wsf'},
                queue=current_app.config['DB']
                )

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


#-------------------------------------------------------------------------------
@main.route('/test_analyze_routes/<days>', methods=['GET'])
@login_required
def test_analyze_routes(days):
    from .. import tasks
    tasks.analyze_upcoming_routes.apply_async(
        kwargs={'days':days},
        queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_build_scheduled_routes', methods=['GET'])
@login_required
def test_build_scheduled_routes():
    from .. import tasks
    tasks.build_scheduled_routes.apply_async(
        queue=current_app.config['DB'])
    return 'OK'


#-------------------------------------------------------------------------------
@main.route('/test_reminder_r1z', methods=['GET'])
@login_required
def test_reminder_scheduler_r1z():
    test_block = 'R1Z'
    test_agency = 'vec'
    test_date = date(2016, 11, 13)

    conf = db['agencies'].find_one({'name': test_agency})

    logger.info('%s: scheduling reminders for %s on %s',
        conf['name'], test_block, test_date.strftime('%b %-d'))

    r = pus.reminder_event(
        conf['name'],
        test_block,
        test_date)

    if r == False:
        logger.info("No reminders created for %s", test_block)

    return redirect(url_for('notify.view_event_list'))

@main.route('/test_reminders', methods=['GET'])
@login_required
def test_reminder_scheduler():
    from .. import tasks
    tasks.schedule_reminders.apply_async(queue=current_app.config['DB'])
    return 'OK'
