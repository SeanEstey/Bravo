
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
from app.notify import pickup_service
from .. import db
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@main.route('/test_non_participant', methods=['GET'])
@login_required
def test_non_participants():
    from .. import tasks
    tasks.find_non_participants.apply_async(queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@main.route('/test_reminder_r1z', methods=['GET'])
@login_required
def test_reminder_scheduler():
    test_block = 'R1Z'
    test_agency = 'vec'
    test_date = date(2016, 11, 13)

    conf = db['agencies'].find_one({'name': test_agency})

    logger.info('%s: scheduling reminders for %s on %s',
        conf['name'], test_block, test_date.strftime('%b %-d'))

    r = pickup_service.create_reminder_event(
        conf['name'],
        test_block,
        test_date)

    if r == False:
        logger.info("No reminders created for %s", test_block)

    return redirect(url_for('notify.view_event_list'))
