from flask import Blueprint, current_app
from flask_login import current_user

api = Blueprint('api', __name__, url_prefix='/api')

@api.before_request
def api_pre_req():
    print 'api current_user=%s' % current_user
    pass

from . import views
