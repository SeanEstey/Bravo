from flask import Blueprint, current_app
from werkzeug.local import LocalProxy

main = Blueprint('main', __name__)
logger = LocalProxy(lambda: current_app.logger)

from . import views
