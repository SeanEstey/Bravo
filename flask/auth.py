import flask
from flask import Flask, request, g, Response, render_template
from flask.ext.login import login_user
from user import User
import json

from app import db, log_handler, login_manager
import reminders
from config import *

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)

def login():
  if request.method == 'GET':
    return render_template('views/login.html')
  elif request.method == 'POST':
    username = request.form['username']
    password = request.form['password']

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
