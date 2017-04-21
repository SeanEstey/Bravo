'''app.auth.views'''
import json, logging
from flask import g, request, render_template, redirect, url_for, jsonify, session
from flask_login import current_user, logout_user, login_required, login_user
from . import auth
from .user import User
from app import get_logger, get_keys
log = get_logger('etap')

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

        return jsonify({'status':'success'})

    return jsonify({'status':'success'})

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
    log.debug('%s logged out', current_user.user_id)
    rv = logout_user()
    return 'OK'
    #return redirect(url_for('main.landing_page'))
