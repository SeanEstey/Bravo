from flask import Blueprint, current_app

routing = Blueprint('routing', __name__, url_prefix='/routing')

from . import views


