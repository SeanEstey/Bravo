'''app.__init__'''
from flask import Blueprint, g

auth = Blueprint('auth', __name__)

from . import views
from .manager import load_user, load_api_user
from flask_login import current_user

@auth.before_request
def before_request():
    print 'before auth request'
    print 'current_user=%s' % current_user
    g.user = current_user
