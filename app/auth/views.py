'''app.auth.views'''
import json, logging
from flask import g, request, render_template, redirect, url_for, jsonify
from flask_login import current_user, logout_user, login_required
from . import auth
from .user import User
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@auth.route('/login', methods=['GET'])
def show_login():
    return render_template('views/login.html')

#-------------------------------------------------------------------------------
@auth.route('/login', methods=['POST'])
def authenticate():
    #print 'auth.authenticate'
    result = User.authenticate(
        request.form.get('username'),
        request.form.get('password'))

    return jsonify(result)

#-------------------------------------------------------------------------------
@auth.route('/logout', methods=['GET'])
@login_required
def logout():
    log.info('User %s logged out', current_user.user_id)
    logout_user()

    return redirect(url_for('main.landing_page'))
