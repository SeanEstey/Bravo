'''app.auth.manager'''
import base64
from bson.objectid import ObjectId
from flask import g, current_app
from flask_login import current_user, login_user, logout_user
from app import login_manager
from .user import User
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def login(username, pw):

    db_user = User.authenticate(username, pw)

    if not db_user:
        log.debug('invalid login credentials for <%s>', username)
        raise Exception("Login failed. Invalid username or password")

    login_user(
        User(
            db_user['user'],
            name = db_user['name'],
            _id = db_user['_id'],
            agency = db_user['agency'],
            admin = db_user['admin']))

    log.debug('%s logged in', username)

#-------------------------------------------------------------------------------
def logout():

    log.debug('%s logged out', current_user.user_id)
    rv = logout_user()

#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):

    db = current_app.db_client['bravo']
    db_user = db.users.find_one({'user': user_id})

    if not db_user:
        log.debug('cant load user_id=%s', user_id)
        return None

    return User(
        user_id,
        name=db_user['name'],
        _id=db_user['_id'],
        agency=db_user['agency'],
        admin=db_user['admin'])

#-------------------------------------------------------------------------------
@login_manager.request_loader
def load_api_user(request):

    api_key = request.headers.get('Authorization')

    if not api_key:
        return None

    api_key = api_key.replace('Basic ', '', 1)

    try:
        api_key = base64.b64decode(api_key)
    except TypeError:
        log.debug('base64 decode error, desc=%s', str(e))
        return None

    api_user = api_key.split(':')[1]

    db = current_app.db_client['bravo']
    user = db.users.find_one({'api_key':str(api_key)})

    if user:
        #print 'loaded api_user %s, group %s' %(user['name'], user['agency'])
        return User(
            user['user'],
            name = user['name'],
            _id = user['_id'],
            agency = user['agency'],
            admin = user['admin'])
    else:
        return None
