'''auth/user.py'''

# Flask user for sessions
class User():
  username = ''
  password = ''
  _id = ''

  def is_authenticated(self):
    return True

  def is_active(self):
    return True

  def is_anonymous(self):
    return False

  def get_id(self):
    try:
        return unicode(self.username)  # python 2
    except NameError:
        return str(self.username)  # python 3

  def __repr__(self):
      return '<User %r>' % (self.username)

  def __init__(self, user, pw):
    self.username = user
    self.password = pw
    #self._id = id
