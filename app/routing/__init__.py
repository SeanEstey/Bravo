from flask import Blueprint

routing = Blueprint('routing', __name__, url_prefix='/routing')

from . import views
