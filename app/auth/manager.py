'''app.auth.manager'''
import logging
import base64
from flask import g
from .. import db_client, login_manager
from .user import User

#-------------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    db = db_client['bravo']
    db_user = db.users.find_one({'user': user_id})

    return User(
        user_id,
        name=db_user['name'],
        _id=db_user['_id'],
        agency=db_user['agency'],
        admin=db_user['admin'])

#-------------------------------------------------------------------------------
@login_manager.request_loader
def load_api_user(request):

	# first, try to login using the api_key url arg
    api_key = request.args.get('api_key')
    if api_key:
        user = User.query.filter_by(api_key=api_key).first()
        if user:
            return user

    # next, try to login using Basic Auth
    api_key = request.headers.get('Authorization')
    #print 'api_key=%s' % api_key

    if api_key:
        api_key = api_key.replace('Basic ', '', 1)
        try:
            api_key = base64.b64decode(api_key)
        except TypeError:
            pass
        #print 'decoded api_key=%s' % api_key

        db = db_client['bravo']
        user = db.users.find_one({'api_key':str(api_key)})

        if user:
            print 'success. loading user=%s' % user['name']

            return User(
                user['user'],
                name = user['name'],
                _id = user['_id'],
                agency = user['agency'],
                admin = user['admin'])
        else:
            print 'no user found for api_key=%s' % api_key

    # finally, return None if both methods did not login the user
    return None
