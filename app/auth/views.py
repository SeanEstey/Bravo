'''auth/views.py'''

import logging
import json
from flask import g, request, render_template, redirect, Response, current_app, url_for
from flask_login import current_user, login_user, logout_user, login_required

from . import auth

from .user import User
from app import db, login_manager
logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
@auth.before_request
def before_request():
    g.user = current_user


#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    user = db['users'].find_one({'username':user_id})
    if user:
        return User(user_id, user.password)
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

    user_match = db['users'].find_one({'user': username})

    if not user_match:
        logger.info("Username '%s' doesnt exist", username)

        return json.dumps({
          'status':'error',
          'title': 'login info',
          'msg':'Username does not exist'})

    if user_match['password'] != password:
        logger.info("User '%s' password is incorrect", username)

        return json.dumps({
            'status':'error',
            'title': 'login info',
            'msg':'Incorrect password'})

    r = json.dumps({
        'status':'success',
        'title': 'yes',
        'msg':'success!'})

    user = User(username, password)

    login_user(user)

    logger.info('User %s logged in', username)

    return Response(response=r, status=200, mimetype='application/json')


#-------------------------------------------------------------------------------
@auth.route('/logout', methods=['GET'])
@login_required
def logout():
    logger.info('logging out')
    logger.info('User %s logged out', current_user.username)
    logout_user()

    return redirect(url_for('main.landing_page'))
