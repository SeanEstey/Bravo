'''app.main.views'''
import logging
from flask import g, request, render_template, redirect, url_for, jsonify, Response
from flask_login import login_required
from .. import get_logger, get_keys
from app.lib import html
from . import main
log = get_logger('main.views')

#-------------------------------------------------------------------------------
@main.route('/')
def landing_page():
    return redirect(url_for('notify.view_event_list'))

#-------------------------------------------------------------------------------
@main.route('/admin')
@login_required
def view_admin():
    if g.user.admin == True:
        settings = get_keys()
        settings.pop('_id')
        settings['google'].pop('oauth')
        settings_html = html.to_div('', settings)
    else:
        settings_html = ''

    return render_template('views/admin.html', agency_config=settings_html)
