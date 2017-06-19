'''app.main.views'''
from flask import g, render_template, redirect, url_for
from flask_login import login_required
from app import get_keys
from . import main

@main.route('/')
@login_required
def landing_page():
    return redirect(url_for('notify.view_event_list'))

@main.route('/recent')
@login_required
def view_recent():
    return render_template('views/recent.html')

@main.route('/admin')
@login_required
def view_admin():
    return render_template('views/admin.html')

@main.route('/tools')
@login_required
def view_tools():
    return render_template(
        'views/tools.html',
        api_key=get_keys('google')['maps_api_key'])

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

