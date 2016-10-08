from celery import Celery
from bson.objectid import ObjectId
from app import celery_app

# Tasks called manually in views

@celery_app.task
def build_route(route_id, job_id=None):
    from app.routing import routes
    return routes.build_route(route_id, job_id=job_id)

@celery_app.task
def add_signup(signup):
    from app import wsf
    return wsf.add_signup(signup)

@celery_app.task
def fire_trigger(evnt_id, trig_id):
    from app.notify import triggers
    return triggers.fire(ObjectId(evnt_id), ObjectId(trig_id))

@celery_app.task
def process_receipts(entries, etapestry_id):
    from app.main import receipts
    return receipts.process(entries, etapestry_id)

@celery_app.task
def create_rfu(agency, request_note, account_number=None, next_pickup=None,
            block=None, date=None, name_address=None):
    from app import gsheets
    return gsheets.create_rfu(agency, request_note, account_number=account_number,
            next_pickup=next_pickup, block=block, date=date,
            name_address=name_address)

@celery_app.task
def cancel_pickup(evnt_id, acct_id):
    from app.notify import pickup_service
    return pickup_service._cancel(evnt_id, acct_id)

# -------- Celerybeat methods ----------

@celery_app.task
def update_sms_accounts():
    from app import sms
    return sms.update_scheduled_accounts_for_sms()

@celery_app.task
def schedule_reminders():
    from app.notify import pickup_service
    return pickup_service.schedule_reminders()

@celery_app.task
def build_routes():
    from app.routing import routes
    return routes.build_scheduled_routes()

@celery_app.task
def monitor_triggers():
    from app.notify import triggers
    #return triggers.monitor_all()
    return True

@celery_app.task
def find_non_participants():
    from app import scheduler
    return scheduler.analyze_non_participants()