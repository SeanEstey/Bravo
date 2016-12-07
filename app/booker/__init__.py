from flask import Blueprint, current_app

booker = Blueprint('booker', __name__, url_prefix='/booker',
template_folder='templates')

from . import views


