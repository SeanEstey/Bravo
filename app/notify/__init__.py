from flask import Blueprint, current_app
#from werkzeug.local import LocalProxy

notify = Blueprint('notify', __name__, url_prefix='/notify')
#logger = LocalProxy(lambda: current_app.logger)

from . import views
