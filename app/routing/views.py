'''routing.views'''

import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import request, jsonify, render_template, redirect, current_app,url_for
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import logging

from . import routing
from . import routes
from .. import utils
from .. import db
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@routing.route('', methods=['GET'])
@login_required
def show_routing():
    agency = db['users'].find_one({'user': current_user.username})['agency']
    agency_conf = db['agencies'].find_one({'name':agency})

    _routes = utils.formatter(
        list(routes.get_metadata()),
        bson_to_json=True,
        to_local_time=True,
        to_strftime="%A %b %d"
    )

    for route in _routes:
        # for storing in route_btn.attr('data-route')
        route['json'] = json.dumps(route)


    from .. import tasks
    tasks.analyze_upcoming_routes.apply_async(
        kwargs={'agency_name':agency,'days':3},
        queue=current_app.config['DB'])

    return render_template(
      'views/routing.html',
      routes=_routes,
      depots=agency_conf['routing']['locations']['depots'],
      drivers=agency_conf['routing']['drivers'],
      admin=db.users.find_one({'user':current_user.username})['admin']
    )

#-------------------------------------------------------------------------------
@routing.route('/get_route/<job_id>', methods=['GET'])
@login_required
def get_route(job_id):
    agency = db['routes'].find_one({'job_id':job_id})['agency']
    conf = db['agencies'].find_one({'name':agency})
    api_key = conf['google']['geocode']['api_key']

    return json.dumps(routes.get_orders(job_id, api_key))

#-------------------------------------------------------------------------------
@routing.route('/analyze_upcoming/<days>', methods=['GET'])
@login_required
def analyze_upcoming(days):
    user = db['users'].find_one({'user': current_user.username})

    from .. import tasks
    tasks.analyze_upcoming_routes.apply_async(
        kwargs={'agency_name':user['agency'],'days':days},
        queue=current_app.config['DB'])
    return 'OK'

#-------------------------------------------------------------------------------
@routing.route('/start_job', methods=['POST'])
@login_required
def get_routing_job_id():
    logger.info('Routing Block %s...', request.form['block'])

    etap_conf = json.loads(request.form['etapestry_id'])

    agency_config = db['agencies'].find_one({
      'name':etap_conf['agency']
    })

    try:
        job_id = routes.submit_job(
          request.form['block'],
          request.form['driver'],
          request.form['date'],
          request.form['start_address'],
          request.form['end_address'],
          etap_conf,
          agency_config['routing']['routific']['api_key'],
          min_per_stop=request.form['min_per_stop'],
          shift_start=request.form['shift_start'])
    except Exception as e:
        logger.error(str(e))
        return False

    return job_id

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
    routes.build_route(route_id, job_id=job_id)
    return redirect(url_for('routing.show_routing'))


#-------------------------------------------------------------------------------
@routing.route('/edit/<route_id>', methods=['POST'])
@login_required
def edit(route_id):
    logger.info(request.form.to_dict())
    logger.info(route_id)

    user = db['users'].find_one({'user': current_user.username})
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
        logger.error('couldnt find value in db for %s:%s',
        request.form['field'], request.form['value'])
        return jsonify({'status':'failed'})

    db.routes.update_one(
        {'_id':ObjectId(route_id)},
        {'$set': {
            request.form['field']: value
    }})

    return jsonify({'status':'success'})
