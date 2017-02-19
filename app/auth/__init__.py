'''app.auth.__init__'''
from flask import Blueprint, g

auth = Blueprint(
    'auth',
    __name__,
    static_folder='static',
    static_url_path='/static/auth',
    template_folder='templates')

from . import views
from .manager import load_user
from flask_login import current_user
