from flask import Blueprint, current_app
from werkzeug.local import LocalProxy

routing = Blueprint('routing', __name__, url_prefix='/routing')
logger = LocalProxy(lambda: current_app.logger)

from . import views


