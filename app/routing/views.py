'''routing.views'''

import logging
import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import request, jsonify, render_template, redirect, current_app,url_for
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from . import routing, main
from .. import sio, task_emit, get_db, utils
log = logging.getLogger(__name__)



#-------------------------------------------------------------------------------
@routing.route('', methods=['GET'])
@login_required
def show_routing():
    db = get_db()
    agency = db['users'].find_one({'user': current_user.user_id})['agency']
    agency_conf = db['agencies'].find_one({'name':agency})

    _routes = utils.formatter(
        list(main.get_metadata()),
        bson_to_json=True,
        to_local_time=True,
        to_strftime="%A %b %d"
    )

    for route in _routes:
        # for storing in route_btn.attr('data-route')
        route['json'] = json.dumps(route)

    import app.tasks
    app.tasks.analyze_upcoming_routes.apply_async(
        kwargs={'agency':agency,'days':5},
        queue=current_app.config['DB'])

    return render_template(
      'views/routing.html',
      routes=_routes,
      depots=agency_conf['routing']['locations']['depots'],
      drivers=agency_conf['routing']['drivers'],
      admin=db.users.find_one({'user':current_user.user_id})['admin'],
      agency=agency
    )

#-------------------------------------------------------------------------------
@routing.route('/get_route/<job_id>', methods=['GET'])
@login_required
def get_route(job_id):
    db = get_db()
    agency = db['routes'].find_one({'job_id':job_id})['agency']
    conf = db['agencies'].find_one({'name':agency})
    api_key = conf['google']['geocode']['api_key']

    return json.dumps(main.get_solution_orders(job_id, api_key))

#-------------------------------------------------------------------------------
@routing.route('/analyze_upcoming/<days>', methods=['GET'])
@login_required
def analyze_upcoming(days):
    db = get_db()
    user = db['users'].find_one({'user': current_user.user_id})

    from .. import tasks
    tasks.analyze_upcoming_routes.apply_async(
        kwargs={'agency_name':user['agency'],'days':days},
        queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@routing.route('/build/<route_id>', methods=['GET', 'POST'])
@login_required
def _build_route(route_id):
    from .. import tasks
    r = tasks.build_route.apply_async(
      args=(route_id,),
      queue=current_app.config['DB']
    )

    return redirect(url_for('routing.show_routing'))

#-------------------------------------------------------------------------------
@routing.route('/build_sheet/<route_id>/<job_id>', methods=['GET'])
@login_required
def _build_sheet(job_id, route_id):
    '''non-celery synchronous func for testing
    '''
    main.build(route_id, job_id=job_id)
    return redirect(url_for('routing.show_routing'))

#-------------------------------------------------------------------------------
@routing.route('/edit/<route_id>', methods=['POST'])
@login_required
def edit(route_id):
    log.info(request.form.to_dict())
    log.info(route_id)

    db = get_db()
    user = db['users'].find_one({'user': current_user.user_id})
    conf = db.agencies.find_one({'name':user['agency']})

    value = None

    if request.form['field'] == 'depot':
        for depot in conf['routing']['locations']['depots']:
            if depot['name'] == request.form['value']:
                value = depot
    elif request.form['field'] == 'driver':
        for driver in conf['routing']['drivers']:
            if driver['name'] == request.form['value']:
                value = driver

    if not value:
        log.error('couldnt find value in db for %s:%s',
        request.form['field'], request.form['value'])
        return jsonify({'status':'failed'})

    db.routes.update_one(
        {'_id':ObjectId(route_id)},
        {'$set': {
            request.form['field']: value
    }})

    return jsonify({'status':'success'})
