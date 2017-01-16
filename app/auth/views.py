'''auth/views.py'''

import logging
import json
from flask import g, request, render_template, redirect, Response, \
current_app, url_for, jsonify, has_app_context
from flask_login import current_user, login_user, logout_user, login_required
from .. import login_manager, get_db
from . import auth
from .user import User, Anonymous
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@auth.before_request
def before_request():
    #log.debug('auth.before_request')
    #g.db = get_db()
    g.user = current_user

#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

#-------------------------------------------------------------------------------
@auth.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'GET':
        return render_template('views/login.html')
    elif request.method == 'POST':
        # login attempt
        if not request.form.get('username'):
            return Response('No username', status=500)

        user_id = request.form['username']
        pw = request.form['password']

        db_user = g.db.users.find_one({'user': user_id})

    if not db_user:
        log.info("DB user doesn't exist | user_id=%s", user_id)

        return json.dumps({
          'status':'error',
          'title': 'login info',
          'msg':'Username does not exist'})

    if db_user['password'] != pw:
        log.info("User '%s' password is incorrect", user_id)

        return json.dumps({
            'status':'error',
            'title': 'login info',
            'msg':'Incorrect password'})

    login_user(User(
        user_id,
        name=db_user['name'],
        _id=db_user['_id'],
        agency=db_user['agency'],
        admin=db_user['admin']))

    log.info('User %s logged in', user_id)

    return jsonify({'status':'success'})

#-------------------------------------------------------------------------------
@auth.route('/logout', methods=['GET'])
@login_required
def logout():
    log.info('User %s logged out', current_user.user_id)
    logout_user()

    return redirect(url_for('main.landing_page'))
