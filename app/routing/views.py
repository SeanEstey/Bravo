import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import request, jsonify, render_template, redirect
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import logging

from . import routing
from . import routes
from app import utils
from app import tasks
#from app.routing import routes

from app import db
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@routing.route('', methods=['GET'])
@login_required
def show_routing():
    agency = db['users'].find_one({'user': current_user.username})['agency']
    agency_conf = db['agencies'].find_one({'name':agency})
    upcoming = routes.get_upcoming_routes(agency)

    return render_template(
      'views/routing.html',
      routes=upcoming,
      depots=agency_conf['routing']['depots'],
      drivers=agency_conf['routing']['drivers']
    )

#-------------------------------------------------------------------------------
@routing.route('/get_scheduled_route', methods=['POST'])
def get_today_route():
    return True
    '''return json.dumps(get_scheduled_route(
      etapestry_id['agency'],
      request.form['block'],
      request.form['date']))
    '''

#-------------------------------------------------------------------------------
@routing.route('/get_route/<job_id>', methods=['GET'])
def get_route(job_id):
    agency = db['routes'].find_one({'job_id':job_id})['agency']
    conf = db['agencies'].find_one({'name':agency})
    api_key = conf['google']['geocode']['api_key']

    return json.dumps(routes.get_orders(job_id, api_key))

#-------------------------------------------------------------------------------
@routing.route('/start_job', methods=['POST'])
def get_routing_job_id():
    logger.info('Routing Block %s...', request.form['block'])

    etap_id = json.loads(request.form['etapestry_id'])

    agency_config = db['agencies'].find_one({
      'name':etap_id['agency']
    })

    try:
        job_id = routes.submit_job(
          request.form['block'],
          request.form['driver'],
          request.form['date'],
          request.form['start_address'],
          request.form['end_address'],
          etap_id,
          agency_config['routing']['routific']['api_key'],
          min_per_stop=request.form['min_per_stop'],
          shift_start=request.form['shift_start'])
    except Exception as e:
        logger.error(str(e))
        return False

    return job_id

#-------------------------------------------------------------------------------
@routing.route('/build/<route_id>', methods=['GET', 'POST'])
def _build_route(route_id):
    r = tasks.build_route.apply_async(
      args=(route_id,),
      queue=current_app.config['DB']
    )

    return redirect(current_app.config['PUB_URL'] + '/routing')

#-------------------------------------------------------------------------------
@routing.route('/build_sheet/<route_id>/<job_id>', methods=['GET'])
def _build_sheet(job_id, route_id):
    '''non-celery synchronous func for testing
    '''
    routes.build_route(route_id, job_id=job_id)
    return redirect(current_app.config['PUB_URL'] + '/routing')


