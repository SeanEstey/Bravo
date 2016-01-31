import flask
from flask import Flask,request,g,Response,url_for
from flask.ext.login import login_user, logout_user, current_user, login_required
from user import User

import app
from app import app, db, logger, login_manager
import reminders
from config import *


def login():
  if request.method == 'GET':
    return render_template('login.html')
  elif request.method == 'POST':
    username = request.form['username']
    password = request.form['password']
    #logger.info('user: %s pw: %s', username, password)
    
    login_record = db['admin_logins'].find_one({'user': username})
    if not login_record:
      r = json.dumps({'status':'error', 'title': 'login info', 'msg':'Username does not exist'})
      logger.info('User %s login failed', username)
    else:
      if login_record['password'] != password:
        r = json.dumps({'status':'error', 'title': 'login info', 'msg':'Incorrect password'})
        logger.info('User %s login failed', username)
      else:
        r = json.dumps({'status':'success', 'title': 'yes', 'msg':'success!'})
        user = load_user(username)
        login_user(user)
        logger.info('User %s logged in', username)

    return Response(response=r, status=200, mimetype='application/json')
 
def load_user(username):
  user_record = db['admin_logins'].find_one({'user':username})

  if user_record:
    user = User(user_record['user'],user_record['password'])
    return user
  else:
    return None
