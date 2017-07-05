# app.main.test_endpoints

from flask import g, request
from flask_login import login_required
from . import main

#-------------------------------------------------------------------------------
@login_required
@main.route('/test_ss', methods=['GET'])
def _test_ss():

    from app import get_keys
    from app.lib.gsheets_cls import SS
    ss_id = get_keys('google')['ss_id']
    oauth = get_keys('google')['oauth']
    ss = SS(oauth, ss_id)
    return 'ok'

#-------------------------------------------------------------------------------
@login_required
@main.route('/test_fire_event', methods=['GET'])
def _test_fire_event():

    from bson import ObjectId as oid
    from app.notify.tasks import fire_trigger

    evnt_id = request.args.get('eid')
    triggers = g.db['triggers'].find({'evnt_id':oid(evnt_id)})

    for trigger in triggers:
        fire_trigger.delay(_id=str(trigger['_id']))

    return 'OK'
