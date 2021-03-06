'''app.auth.user'''
import logging
from flask import current_app
from flask_login import AnonymousUserMixin, UserMixin, login_user
#from app import db_client

class User():

    _id = ''
    user_id = ''
    group = ''
    admin = False
    developer = False
    email = ''
    name = ''

    #---------------------------------------------------------------------------
    def __repr__(self):
        return '<user_id %r>' % self.user_id

    #---------------------------------------------------------------------------
    def get_name(self):
        return self.name

    #---------------------------------------------------------------------------
    def to_dict(self):
        user_dict = self.__dict__
        user_dict['_id'] = str(user_dict['_id'])
        return user_dict

    #---------------------------------------------------------------------------
    def is_admin(self):
        return self.admin

    #---------------------------------------------------------------------------
    def is_authenticated(self):
        return True

    #---------------------------------------------------------------------------
    def is_active(self):
        return True

    #---------------------------------------------------------------------------
    def is_anonymous(self):
        return False

    #---------------------------------------------------------------------------
    def get_id(self):
        try:
            return unicode(self.user_id)  # python 2
        except NameError:
            return str(self.user_id)  # python 3

    #---------------------------------------------------------------------------
    @classmethod
    def authenticate(cls, user_id, pw):

        if not user_id or not pw:
            return None

        db = current_app.db_client['bravo']
        db_user = db.users.find_one({
            'user': user_id,
            'password': pw})

        if not db_user:
            return None
        else:
            return db_user

    #---------------------------------------------------------------------------
    def __init__(self, user_id, name=None, _id=None, group=None, admin=False):

        self._id = _id
        self.user_id = user_id
        self.email = user_id
        self.name = name
        self.group = group
        self.admin = admin

class Anonymous(AnonymousUserMixin):

    #---------------------------------------------------------------------------
    def __init__(self, user_id=None):

        self.user_id = user_id or 'anon'
        self._id = None
        self.group = 'anon'
