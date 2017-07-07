'''booker.views'''
from datetime import datetime, date, time, timedelta
from flask import g, request, jsonify, render_template
from flask_login import login_required
from app import get_keys
from . import booker
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
@booker.route('/', methods=['GET'])
@login_required
def show_home():

    from json import dumps, loads
    return render_template(
        'views/booker.html',
        city_coords=dumps(get_keys('routing')['locations']['city']['coords']),
        home_coords=dumps(get_keys('routing')['locations']['office']['coords']),
        api_key=get_keys('google')['maps_api_key']
    )
