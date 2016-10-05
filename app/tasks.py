from celery import Celery
from bson.objectid import ObjectId
from app import celery_app

import wsf
import triggers
import gsheets
import pickup_service
import routing
import receipts
import scheduler
import sms

# Tasks called manually in views

@celery_app.task
def build_route(route_id, job_id=None):
    return routing.build_route(route_id, job_id=job_id)

@celery_app.task
def add_signup(signup):
    return wsf.add_signup(signup)

@celery_app.task
def fire_trigger(event_id, trig_id):
    return triggers.fire(ObjectId(event_id), ObjectId(trig_id))

@celery_app.task
def process_receipts(entries, etapestry_id):
    return receipts.process(entries, etapestry_id)

@celery_app.task
def create_rfu(agency, request_note, account_number=None, next_pickup=None,
            block=None, date=None, name_address=None):
    return gsheets.create_rfu(agency, request_note, account_number=account_number,
            next_pickup=next_pickup, block=block, date=date,
            name_address=name_address)

@celery_app.task
def cancel_pickup(event_id, account_id):
    return pickup_service._cancel(event_id, account_id)

# -------- Celerybeat methods ----------

@celery_app.task
def update_sms_accounts():
    return sms.update_scheduled_accounts_for_sms()

@celery_app.task
def create_scheduled_events():
    return pickup_service.create_scheduled_events()

@celery_app.task
def build_todays_routes():
    return routing.build_todays_routes()

@celery_app.task
def monitor_triggers():
    return triggers.monitor_all()

@celery_app.task
def find_non_participants():
    return scheduler.analyze_non_participants()
