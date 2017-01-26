'''auth/user.py'''
import logging
from flask_login import AnonymousUserMixin, UserMixin, login_user
from app import db_client
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
class User():
    def __repr__(self):
        return '<user_id %r>' % self.user_id

    _id = ''
    user_id = ''
    agency = ''
    admin = False
    developer = False
    email = ''
    name = ''

    def get_name(self):
        return self.name

    def is_admin(self):
        return self.admin

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.user_id)  # python 2
        except NameError:
            return str(self.user_id)  # python 3

    @classmethod
    def authenticate(cls, user_id, pw):
        log.debug('User.authenticate() user_id=%s, pw=%s', user_id, pw)

        if not user_id or not pw:
            return None
            #return Response('No username', status=500)

        db = db_client['bravo']
        db_user = db.users.find_one({
            'user': user_id,
            'password': pw})

        if not db_user:
            log.error('invalid credentials, user_id=%s', user_id)
            return None
        else:
            return db_user

        '''
        login_user(
            User(
                user_id,
                name = usr['name'],
                _id = usr['_id'],
                agency = usr['agency'],
                admin = usr['admin']))
        log.debug('logged in %s', user_id)
        #return {'status':'success', 'user_id':user_id}
        '''

    def __init__(self, user_id, name=None, _id=None, agency=None, admin=False):
        self._id = _id
        self.user_id = user_id
        self.email = user_id
        self.name = name
        self.agency = agency
        self.admin = admin

#-------------------------------------------------------------------------------
class Anonymous(AnonymousUserMixin):
    def __init__(self):
        #log.debug('loading guest')
        self.user_id = 'Guest'
        self._id = None

#-------------------------------------------------------------------------------
class API(UserMixin):
    def get_id(self):
        try:
            return unicode(self.user_id)  # python 2
        except NameError:
            return str(self.user_id)  # python 3

