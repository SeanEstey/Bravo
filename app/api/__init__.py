from flask import Blueprint, current_app

api = Blueprint('api', __name__, url_prefix='/api')

from . import views
