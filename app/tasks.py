from celery import Celery
from bson.objectid import ObjectId
from app import celery_app

#celery_app = Celery(include=['tasks'])
#celery_app.config_from_object('celeryconfig')

# Register tasks from modules

from wsf import add_signup
from triggers import fire, monitor_all
'''from gsheets import create_rfu

from pickup_service import add_future_pickups, schedule_reminder_events, _cancel
from routing import build_route, build_todays_routes
from receipts import process
from scheduler import analyze_non_participants
from sms import update_scheduled_accounts_for_sms
'''

@celery_app.task
def do_add_signup(signup):
    add_signup(signup)

@celery_app.task
def monitor_triggers():
    monitor_all()

@celery_app.task
def process_receipts(entries, etapestry_id):
    process(entries, etapestry_id)

@celery_app.task
def make_rfu(agency, request_note, account_number=None, next_pickup=None,
            block=None, date=None, name_address=None):
    create_rfu(agency, request_note, account_number=account_number,
            next_pickup=next_pickup, block=block, date=date,
            name_address=name_address)

@celery_app.task
def cancel_pickup(event_id, account_id):
    _cancel(event_id, account_id)

@celery_app.task
def fire_trigger(event_id, trig_id):
    fire(ObjectId(event_id), ObjectId(trig_id))
