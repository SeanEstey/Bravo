'''auth/views.py'''

import logging
import json
from flask import g, request, render_template, redirect, Response, \
current_app, url_for, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from .. import login_manager, get_db
from . import auth
from .user import User
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@auth.before_request
def before_request():
    #log.debug('auth.before_request')
    g.db = get_db()
    g.user = current_user

#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    user = g.db.users.find_one({'user':user_id})

    if user:
        return User(
            user_id,
            user['password'],
            agency=user['agency'],
            admin=user.get('admin'))
    else:
        return None

#-------------------------------------------------------------------------------
@auth.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'GET':
        return render_template('views/login.html')
    elif request.method == 'POST':
        # login attempt
        if not request.form.get('username'):
            return Response('No username', status=500)

        username = request.form['username']
        password = request.form['password']

        user_match = g.db.users.find_one({'user': username})

    if not user_match:
        log.info("Username '%s' doesnt exist", username)

        return json.dumps({
          'status':'error',
          'title': 'login info',
          'msg':'Username does not exist'})

    if user_match['password'] != password:
        log.info("User '%s' password is incorrect", username)

        return json.dumps({
            'status':'error',
            'title': 'login info',
            'msg':'Incorrect password'})

    user = User(
        username,
        password,
        user_match['agency'])

    login_user(user)

    log.info('User %s logged in', username)

    return jsonify({'status':'success'})

#-------------------------------------------------------------------------------
@auth.route('/logout', methods=['GET'])
@login_required
def logout():
    log.info('User %s logged out', current_user.username)
    logout_user()

    return redirect(url_for('main.landing_page'))
