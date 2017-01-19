'''routing.views'''

import logging
import json
import twilio.twiml
import requests
from datetime import datetime, date, time, timedelta
from flask import g, request, jsonify, render_template, redirect, current_app,url_for
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from . import routing, main
from .. import sio, get_db, utils
from .tasks import analyze_routes, build_route
log = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@routing.route('', methods=['GET'])
@login_required
def show_routing():
    _routes = utils.formatter(
        list(main.get_metadata()),
        bson_to_json=True,
        to_local_time=True,
        to_strftime="%A %b %d"
    )

    for route in _routes:
        # for storing in route_btn.attr('data-route')
        route['json'] = json.dumps(route)

    analyze_routes.delay(kwargs={'days':5})

    conf = g.db.agencies.find_one({'name':g.user.agency})
    return render_template(
      'views/routing.html',
      routes=_routes,
      depots=conf['routing']['locations']['depots'],
      drivers=conf['routing']['drivers'],
      admin=g.user.admin,
      agency=g.user.agency
    )

#-------------------------------------------------------------------------------
@routing.route('/get_route/<job_id>', methods=['GET'])
@login_required
def get_route(job_id):
    conf = g.db.agencies.find_one({'name':g.user.agency})

    return json.dumps(main.get_solution_orders(
        job_id,
        conf['google']['geocode']['api_key']))

#-------------------------------------------------------------------------------
@routing.route('/analyze_upcoming/<days>', methods=['GET'])
@login_required
def analyze_upcoming(days):
    analyze_routes.delay(kwargs={'days':days})
    return 'OK'

#-------------------------------------------------------------------------------
@routing.route('/build/<route_id>', methods=['GET', 'POST'])
@login_required
def _build_route(route_id):
    build_route.delay(args=(route_id,))
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

    value = None

    if request.form['field'] == 'depot':
        for depot in get_keys('routing')['locations']['depots']:
            if depot['name'] == request.form['value']:
                value = depot
    elif request.form['field'] == 'driver':
        for driver in get_keys('routing')['drivers']:
            if driver['name'] == request.form['value']:
                value = driver

    if not value:
        log.error('couldnt find value in db for %s:%s',
        request.form['field'], request.form['value'])
        return jsonify({'status':'failed'})

    g.db.routes.update_one(
        {'_id':ObjectId(route_id)},
        {'$set': {
            request.form['field']: value
    }})

    return jsonify({'status':'success'})
