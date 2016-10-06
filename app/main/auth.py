import flask
from flask import Flask, request, g, Response, render_template
from flask.ext.login import login_user, logout_user, login_required
from app.main.user import User
import json
import logging

from app import app, db, login_manager
logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def logout():
    logout_user()

#-------------------------------------------------------------------------------
def login():
    if request.method == 'GET':
        return render_template('views/login.html')
    elif request.method == 'POST':
        # login attempt
        if not request.form.get('username'):
            return Response('No username', status=500)

        username = request.form['username']
        password = request.form['password']

    login_record = db['users'].find_one({'user': username})

    if not login_record:
        r = json.dumps({
          'status':'error',
          'title': 'login info',
          'msg':'Username does not exist'})

        logger.info('User %s login failed', username)
    else:
        if login_record['password'] != password:
            r = json.dumps({
                'status':'error',
                'title': 'login info',
                'msg':'Incorrect password'})

            logger.info('User %s login failed', username)
        else:
            r = json.dumps({
                'status':'success',
                'title': 'yes',
                'msg':'success!'})

            user = load_user(username)
            login_user(user)

            logger.info('User %s logged in', username)

    return Response(response=r, status=200, mimetype='application/json')


#-------------------------------------------------------------------------------
def load_user(username):
    user_record = db['users'].find_one({'user':username})

    if user_record:
        user = User(user_record['user'],user_record['password'])
        return user
    else:
        return None
