'''app.auth.views'''
import json, logging
from flask import g, request, render_template, redirect, url_for, jsonify, session
from flask_login import current_user, logout_user, login_required, login_user
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
    db_user = User.authenticate(
        request.form.get('username'),
        request.form.get('password'))

    if db_user:
        login_user(
            User(
                db_user['user'],
                name = db_user['name'],
                _id = db_user['_id'],
                agency = db_user['agency'],
                admin = db_user['admin']))
        log.debug('%s logged in', current_user)

    return redirect(url_for('notify.view_event_list'))

#-------------------------------------------------------------------------------
@login_required
@auth.route('/logout', methods=['GET'])
def client_logout():
    logout_user()
    return redirect(url_for('main.landing_page'))

#-------------------------------------------------------------------------------
@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    rv = logout_user()
    #log.debug('User %s logged out. rv=%s', current_user.user_id, rv)
    return 'OK'
    #return redirect(url_for('main.landing_page'))
