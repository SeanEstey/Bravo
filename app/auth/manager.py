'''app.auth.manager'''
import logging
import base64
from bson.objectid import ObjectId
from flask import g
from flask_login import current_user, login_user
from .. import db_client, login_manager
from app.utils import print_vars
from .user import User
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):

    #log.debug('load_user() user_id=%s', user_id)
    db = db_client['bravo']
    db_user = db.users.find_one({'user': user_id})

    if not db_user:
        log.debug('cant load user_id=%s', user_id)
        return None

    user = User(
        user_id,
        name=db_user['name'],
        _id=db_user['_id'],
        agency=db_user['agency'],
        admin=db_user['admin'])

    #log.debug('user_loader returning user_id=%s', user.user_id)
    return user

#-------------------------------------------------------------------------------
@login_manager.request_loader
def load_api_user(request):

    #log.debug('request_loader(). form=%s', request.form.to_dict())

	# first, try to login using user_id/pw

    username = request.form.get('username')
    password = request.form.get('password')

    if username and password:
        db_user = User.authenticate(
            request.form.get('username'),
            request.form.get('password'))

        if db_user:
            log.debug('request_loader returning user_id=%s', db_user['user'])

            user = User(
                db_user['user'],
                name = db_user['name'],
                _id = db_user['_id'],
                agency = db_user['agency'],
                admin = db_user['admin'])

            log.debug('logging in')
            login_user(user)

            return user

    # next, try to login using Basic Auth

    #log.debug('trying API auth login')
    api_key = request.headers.get('Authorization')

    if api_key:
        api_key = api_key.replace('Basic ', '', 1)
        try:
            api_key = base64.b64decode(api_key)
        except TypeError:
            log.debug('base64 decode error, desc=%s', str(e))
            pass

        #log.debug('got api_key=%s', api_key)
        api_user = api_key.split(':')[1]

        #if not ObjectId.is_valid(api_user):
        #    return None

        db = db_client['bravo']
        user = db.users.find_one({'api_key':str(api_key)})

        if user:
            log.debug('"%s" API auth success', user['name'])

            return User(
                user['user'],
                name = user['name'],
                _id = user['_id'],
                agency = user['agency'],
                admin = user['admin'])
        else:
            log.debug('no user found for api_key=%s', api_key)

    # finally, return None if both methods did not login the user
    #log.debug('failed to load api user. return none')
    return None
