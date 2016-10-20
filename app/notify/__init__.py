from flask import Blueprint, current_app

notify = Blueprint('notify', __name__, url_prefix='/notify',
template_folder='templates')

from . import views
