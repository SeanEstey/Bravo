# app.main.views

from flask import g, render_template, redirect, url_for
from flask_login import login_required
from app import get_keys
from . import main # Blueprint

#-------------------------------------------------------------------------------
@main.route('/')
@login_required
def landing_page():

    return redirect(url_for('notify.view_event_list'))

#-------------------------------------------------------------------------------
@main.route('/accounts')
@login_required
def view_accounts():

    from json import dumps
    city_coords = dumps(get_keys('routing')['locations']['city']['coords'])
    home_coords = dumps(get_keys('routing')['locations']['office']['coords'])

    return render_template(
        'views/accounts.html',
        api_key=get_keys('google')['maps_api_key'],
        city_coords = city_coords,
        home_coords = home_coords)

#-------------------------------------------------------------------------------
@main.route('/recent')
@login_required
def view_recent():

    return render_template(
        'views/recent.html',
        org_name = g.group
    )

#-------------------------------------------------------------------------------
@main.route('/admin')
@login_required
def view_admin():

    return render_template('views/admin.html')

#-------------------------------------------------------------------------------
@main.route('/tools')
@login_required
def view_tools():

    return render_template(
        'views/map_analyzer.html',
        api_key=get_keys('google')['maps_api_key'])

#-------------------------------------------------------------------------------
@main.route('/analytics')
@login_required
def view_analytics():

    return render_template('views/analytics.html')

#-------------------------------------------------------------------------------
@main.route('/datatable')
@login_required
def view_datatable():

    return render_template('views/datatable.html')

#-------------------------------------------------------------------------------
@main.route('/map/<block>')
@login_required
def view_map(block):

    from json import dumps
    city_coords = dumps(get_keys('routing')['locations']['city']['coords'])
    home_coords = dumps(get_keys('routing')['locations']['office']['coords'])

    return render_template(
        'views/map.html',
        api_key=get_keys('google')['maps_api_key'],
        city_coords = city_coords,
        home_coords = home_coords,
        block = block
    )

