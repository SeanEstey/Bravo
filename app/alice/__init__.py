from flask import Blueprint, current_app

booker = Blueprint('alice', __name__, url_prefix='/alice',
template_folder='templates')

from . import views


