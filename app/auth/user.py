'''auth/user.py'''
from flask_login import AnonymousUserMixin

#-------------------------------------------------------------------------------
class User():
    _id = ''
    user_id = ''
    agency = ''
    admin = ''
    email = ''
    name = ''

    def get_name(self):
        return self.name

    def get_agency(self):
        return self.agency

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

    def __repr__(self):
        return '<user_id %r>' % (self.user_id)

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
        self.user_id = 'Guest'
