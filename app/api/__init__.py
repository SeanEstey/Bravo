'''app.api.__init__'''
from flask import g, Blueprint
from flask_login import current_user

api = Blueprint(
    'api',
    __name__,
    url_prefix='/api')

@api.before_request
def api_pre_req():
    g.user = current_user

from . import views
