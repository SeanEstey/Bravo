'''app.auth.__init__'''
import logging
from flask import Blueprint, g

auth = Blueprint('auth', __name__)

from . import views
from .manager import load_user #load_api_user
from flask_login import current_user
log = logging.getLogger(__name__)

@auth.before_request
def before_request():
    #log.debug('auth.before_request')
    pass
