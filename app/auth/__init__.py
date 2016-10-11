from flask import Blueprint, current_app
from werkzeug.local import LocalProxy

auth = Blueprint('auth', __name__)
logger = LocalProxy(lambda: current_app.logger)

from . import views
