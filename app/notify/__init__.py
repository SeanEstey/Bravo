from flask import Blueprint

notify = Blueprint('notify', __name__, url_prefix='/notify')

from . import views
